# -*- encoding: utf-8 -*-
"""
weirwood.core.services.tel_event_service module

Service and MongoDB document model for TEL (Transaction Event Log) events.
Weirwood acts as an active registrar backer: it parses, signs, and stores
each TEL event it receives, returning its signature as a backer receipt.
"""
from datetime import datetime

from keri.core import coring
from keri.help import ogler
from mongoengine import (
    BinaryField, DateTimeField, Document, IntField, StringField
)

from weirwood.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()

# TEL event types
_REGISTRY_EVENTS = frozenset(("vcp", "vrt"))
_CREDENTIAL_EVENTS = frozenset(("iss", "bis", "rev", "brv"))


def _extract_fields(ked: dict) -> tuple[str, str, str | None, int]:
    """
    Extract (event_type, regk, vcid, sn) from a TEL event KED.

    Registry-level events (vcp/vrt):
        vcp: regk = said (the vcp SAID IS the registry prefix)
        vrt: regk = ked['i']
    Credential-level events (iss/rev/bis/brv):
        iss/rev: regk = ked['ri'],  vcid = ked['i']
        bis/brv: regk = ked['ii'], vcid = ked['i']
    """
    event_type = ked.get("t", "")
    sn_raw = ked.get("s", 0)
    sn = int(sn_raw, 16) if isinstance(sn_raw, str) else int(sn_raw)

    if event_type == "vcp":
        regk = ked.get("d", "")   # regk IS the SAID of the vcp event
        vcid = None
    elif event_type == "vrt":
        regk = ked.get("i", "")
        vcid = None
    elif event_type in ("iss", "rev"):
        regk = ked.get("ri", "")
        vcid = ked.get("i")
    elif event_type in ("bis", "brv"):
        regk = ked.get("ii", "")
        vcid = ked.get("i")
    else:
        regk = ked.get("i", "")
        vcid = None

    return event_type, regk, vcid, sn


class TelEvent(Document):
    """A TEL event stored and receipted by weirwood as registrar backer."""
    said = StringField(required=True, primary_key=True)
    regk = StringField(required=True)          # registry prefix (AID)
    vcid = StringField()                       # credential SAID (iss/bis/rev/brv only)
    sn = IntField(required=True, default=0)
    event_type = StringField(required=True)    # vcp | vrt | iss | bis | rev | brv
    raw = BinaryField(required=True)           # raw CESR-encoded event bytes
    receipt = StringField()                    # weirwood's cigar signature (qb64)
    created_at = DateTimeField(default=datetime.now)

    meta = {
        "indexes": ["regk", "vcid"],
        "ordering": ["sn"],
    }


class TelEventService:
    """
    Receives, signs, and stores TEL events on behalf of the weirwood registrar hab.

    On each received event weirwood:
      1. Attempts to parse via the existing tvy/parser pipeline.
      2. Extracts event metadata from the CESR-encoded KED.
      3. Signs the raw bytes with the weirwood hab (unindexed cigar).
      4. Persists the TelEvent document.
      5. Returns the document and the qb64-encoded receipt signature.
    """

    def __init__(self, hby, tvy, parser, hab):
        self.hby = hby
        self.tvy = tvy
        self.parser = parser
        self.hab = hab

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def receive_event(self, raw: bytes) -> tuple["TelEvent", str]:
        """
        Parse, sign, and store a TEL event.

        Args:
            raw: Raw CESR-encoded TEL event bytes.

        Returns:
            (TelEvent, receipt_qb64) — the stored document and weirwood's
            backer signature over the raw bytes.

        Raises:
            ConflictError: If an event with the same SAID already exists.
            ValueError: If raw bytes cannot be parsed as a KERI event.
        """
        # Parse the event header to extract metadata
        try:
            serder = coring.Serder(raw=raw)
        except Exception as e:
            raise ValueError(f"Cannot parse TEL event bytes: {e}")

        said = serder.said
        event_type, regk, vcid, sn = _extract_fields(serder.ked)

        if not event_type:
            raise ValueError("TEL event missing 't' (ilk) field")
        if not regk:
            raise ValueError(f"TEL event {said} missing registry prefix field")

        if TelEvent.objects(said=said).first():
            raise ConflictError(f"TEL event already exists: {said}")

        # Attempt keripy pipeline processing (may escrow if anchor not yet available)
        try:
            ims = bytearray(raw)
            self.parser.parse(ims=ims, tvy=self.tvy, local=True)
        except Exception as e:
            logger.warning(f"TEL event {said} could not be fully validated: {e}. "
                           "Storing as pending.")

        # Sign raw bytes with weirwood hab (unindexed cigar — backer receipt format)
        try:
            cigars = self.hab.sign(ser=raw, indexed=False)
            receipt_qb64 = cigars[0].qb64
        except Exception as e:
            logger.error(f"Failed to sign TEL event {said}: {e}")
            receipt_qb64 = ""

        event = TelEvent(
            said=said,
            regk=regk,
            vcid=vcid,
            sn=sn,
            event_type=event_type,
            raw=raw,
            receipt=receipt_qb64,
        )
        event.save()
        logger.info(f"Stored TEL event {event_type} said={said} regk={regk}")
        return event, receipt_qb64

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def get_events_for_registry(self, regk: str) -> list["TelEvent"]:
        """Return all TEL events for a given registry prefix, ordered by sn."""
        return list(TelEvent.objects(regk=regk).order_by("sn"))

    def get_event(self, said: str) -> "TelEvent":
        """Fetch a single TelEvent by its SAID. Raises NotFoundError if missing."""
        try:
            return TelEvent.objects.get(said=said)
        except TelEvent.DoesNotExist:
            raise NotFoundError(f"TEL event not found: {said}")

    def get_events_for_credential(self, regk: str, vcid: str) -> list["TelEvent"]:
        """Return all TEL events for a specific credential SAID within a registry."""
        return list(TelEvent.objects(regk=regk, vcid=vcid).order_by("sn"))