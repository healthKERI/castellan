# -*- encoding: utf-8 -*-
"""
castellan.core.services.issued_credential_service module

Service and MongoDB document model for credentials issued by this account.
"""

import math
from datetime import datetime
from typing import Optional

from keri import core, kering
from keri.app.habbing import Habery
from keri.core import coring, serdering
from keri.db import dbing
from keri.help import ogler, helping
from mongoengine import (
    BooleanField,
    DateTimeField,
    DictField,
    Document,
    Q,
    StringField,
    ListField,
    DoesNotExist,
    EmbeddedDocumentField,
    IntField,
    EmbeddedDocument,
)

from castellan.core.services.custom.custom_errors import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from castellan.core.services.dynamic_fields import DynamicField, create_dynamic_field

logger = ogler.getLogger()


def flatten_values(obj) -> str:
    """Recursively extract all scalar values from a nested dict/list into a space-joined string."""
    parts = []
    if isinstance(obj, dict):
        for v in obj.values():
            parts.append(flatten_values(v))
    elif isinstance(obj, list):
        for item in obj:
            parts.append(flatten_values(item))
    elif obj is not None:
        parts.append(str(obj))
    return " ".join(p for p in parts if p)


def flatten_dynamic_fields(dynamic_fields) -> str:
    """Extract searchable text from dynamic fields list."""
    parts = []
    for field in dynamic_fields:
        if hasattr(field, "get_value_for_search"):
            parts.append(field.get_value_for_search())
    return " ".join(parts)


class TELAnc(EmbeddedDocument):
    """Transaction Anchor to KEL event"""

    prefix = StringField(required=True)
    sn = IntField(required=True)  # Sequence number
    said = StringField(required=True)


class IssuedCredential(Document):
    """ACDC credential issued by this account to a recipient."""

    said = StringField(required=True, primary_key=True)
    sad = DictField(required=True)
    issuer = StringField(required=True)  # account AID (us)
    schema_said = StringField(required=True)
    schema_title = StringField(required=True)
    recipient = StringField()  # holder AID
    status = StringField()  # "issued" | "revoked"
    anc = EmbeddedDocumentField(TELAnc)  # TEL anchor
    published = BooleanField(default=False)
    notes = StringField(required=False)
    dynamic_fields = ListField(EmbeddedDocumentField(DynamicField), default=list)
    search_text = StringField(db_field="_search_text")  # flattened sad values
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class TELEvent(Document):
    """Transaction Event Log Event Model"""

    said = StringField(required=True, primary_key=True)  # Self-addressing identifier
    credential_said = StringField(required=True)  # Reference to credential
    sn = IntField(required=True)  # Sequence number
    sad = DictField(required=True)  # Serialized event data
    anc = EmbeddedDocumentField(TELAnc)  # Signature cigars
    dts = StringField(required=True)  # Datetime stamp
    created_at = DateTimeField(default=datetime.now)


class IssuedCredentialService:
    """Service for managing credentials issued by this account."""

    def __init__(
        self,
        hby: Optional[Habery] = None,
        rgy=None,
        tvy=None,
        parser=None,
        kel_svc=None,
        field_tracking_svc=None,
    ):
        self.hby = hby
        self.rgy = rgy
        self.tvy = tvy
        self.parser = parser
        self.reger = rgy.reger if rgy is not None else None
        self.kel_svc = kel_svc
        self.field_tracking_svc = field_tracking_svc

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @staticmethod
    def list_credentials(
        filter=None,
        issuer=None,
        recipient=None,
        status=None,
        published=None,
        page=0,
        page_size=20,
        order=None,
    ):
        """
        Return a page of IssuedCredential documents matching the given filters.

        Args:
            filter: Case-insensitive string searched across all document fields
                    and all sad dict values (via _search_text).
            issuer: Exact match on issuer AID.
            recipient: Exact match on recipient AID.
            status: Exact match on status string.
            published: Boolean filter on published flag.
            page: Zero-indexed page number.
            page_size: Number of results per page (default 20).
            order: MongoEngine order_by string or list of strings,
                   e.g. "+created_at" or ["-said", "+issuer"].

        Returns:
            (credentials_list, total_count, num_pages)
        """
        qs = IssuedCredential.objects()

        # Exact-match filters
        if issuer is not None:
            qs = qs.filter(issuer=issuer)
        if recipient is not None:
            qs = qs.filter(recipient=recipient)
        if status is not None:
            qs = qs.filter(status=status)
        if published is not None:
            qs = qs.filter(published=published)

        # Free-text search across fixed fields and sad values
        if filter:
            qs = qs.filter(
                Q(said__icontains=filter)
                | Q(issuer__icontains=filter)
                | Q(recipient__icontains=filter)
                | Q(status__icontains=filter)
                | Q(search_text__icontains=filter)
            )

        # Ordering
        if order:
            if isinstance(order, str):
                order = [order]
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        credentials = list(qs.skip(page * page_size).limit(page_size))

        return credentials, total, num_pages

    @staticmethod
    def get_credential(said: str):
        """Fetch a single IssuedCredential by SAID. Raises NotFoundError if missing."""
        try:
            cred = IssuedCredential.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Issued credential not found: {said}")
        except Exception as e:
            raise RuntimeError(f"Error querying issued credential: {e}")
        return cred

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def save_credential(self, doc: dict, acdc: bytes):
        """
        Parse an ACDC stream and persist an IssuedCredential record.

        Args:
            doc: Metadata dict with keys: said, issuer, recipient, schema,
                 status (optional), published (optional).
            acdc: Raw ACDC bytes to parse into Regery/Tevery.

        Returns:
            The created IssuedCredential document.

        Raises:
            ValidationError: If required fields are missing.
            ConflictError: If a record with the same SAID already exists.
            NotFoundError: If the issuer AID is not known.
            RuntimeError: If ACDC parsing fails.
        """
        issuer = doc.get("issuer")
        if not issuer:
            raise ValidationError("Missing required field: issuer")

        said = doc.get("said")
        if not said:
            raise ValidationError("Missing required field: said")

        if issuer not in self.hby.kevers:
            raise NotFoundError(f"Issuer AID not found in kevers: {issuer}")

        if IssuedCredential.objects(said=said).first():
            raise ConflictError(f"Issued credential already exists: {said}")

        self.kel_svc.get_keystate(issuer)

        try:
            self.parser.parse(ims=bytearray(acdc), tvy=self.tvy, local=False)
        except Exception as e:
            raise RuntimeError(f"Error parsing ACDC stream: {e}")

        creder = self.reger.creds.get(keys=(said,))
        if creder is None:
            raise RuntimeError(f"Credential {said} not found in reger after parsing")

        return self._capture(creder, doc)

    def _capture(self, creder, doc: dict):
        """Build and persist an IssuedCredential from a parsed SerderACDC."""
        regk = creder.regi
        status_text = "issued"
        try:
            vc_state = self.rgy.tevers[regk].vcState(creder.said)
            if vc_state.et in [coring.Ilks.rev, coring.Ilks.brv]:
                status_text = "revoked"
        except Exception:
            pass

        search_parts = [flatten_values(creder.attrib)]

        # Handle dynamic_fields from doc
        dynamic_fields_data = doc.get("dynamic_fields", [])
        dynamic_fields = []
        if dynamic_fields_data:
            try:
                dynamic_fields = [
                    create_dynamic_field(fd) for fd in dynamic_fields_data
                ]
                search_parts.append(flatten_dynamic_fields(dynamic_fields))
            except ValueError as e:
                logger.warning(f"Invalid dynamic field data: {e}")

        search_text = " ".join(search_parts)

        prefixer, seqner, saider = self.reger.cancs.get(keys=(creder.said,))
        anc = TELAnc(prefix=prefixer.qb64, sn=seqner.sn, said=saider.qb64)

        cred = IssuedCredential(
            said=creder.said,
            sad=creder.sad,
            issuer=creder.issuer,
            schema_said=doc.get("schema_said", ""),
            schema_title=doc.get("schema_title", ""),
            recipient=creder.issuee or doc.get("recipient"),
            status=status_text,
            published=doc.get("publish", False),
            dynamic_fields=dynamic_fields,
            search_text=search_text,
            anc=anc,
        )
        cred.save()
        logger.info(f"Saved issued credential: {creder.said}")

        # 4. Capture TEL events
        self.capture_tel_events(creder.issuer, regk, creder.said)

        # Track dynamic fields for this schema
        if self.field_tracking_svc is not None and dynamic_fields:
            try:
                schema_said = doc.get("schema_said")
                if schema_said:
                    self.field_tracking_svc.track_fields(schema_said, dynamic_fields)
            except Exception as e:
                logger.warning(f"Could not track fields for schema: {e}")

        return cred

    def update_credential(self, said: str, update_data: dict):
        """
        Update allowed fields on an IssuedCredential.

        Allowed fields: status, published, recipient, notes, dynamic_fields.
        """
        cred = self.get_credential(said)
        try:
            # Handle simple field updates
            for field in ("status", "published", "recipient", "notes"):
                if field in update_data:
                    setattr(cred, field, update_data[field])

            # Handle dynamic_fields updates
            if "dynamic_fields" in update_data:
                dynamic_fields_data = update_data["dynamic_fields"]
                if not isinstance(dynamic_fields_data, list):
                    raise ValidationError("dynamic_fields must be a list")

                # Validate and create dynamic field objects
                dynamic_fields = [
                    create_dynamic_field(fd) for fd in dynamic_fields_data
                ]
                cred.dynamic_fields = dynamic_fields

                # Rebuild search_text
                search_parts = [flatten_values(cred.sad)]
                if dynamic_fields:
                    search_parts.append(flatten_dynamic_fields(dynamic_fields))
                cred.search_text = " ".join(search_parts)

            cred.updated_at = datetime.now()
            cred.save()
        except ValidationError:
            raise
        except ValueError as e:
            raise ValidationError(f"Invalid dynamic field data: {e}")
        except Exception as e:
            raise RuntimeError(f"Error updating issued credential: {e}")

        logger.info(f"Updated issued credential: {said}")
        return cred

    def delete_credential(self, said: str):
        """Delete an IssuedCredential. Raises NotFoundError if missing."""
        cred = self.get_credential(said)
        try:
            cred.delete()
        except Exception as e:
            raise RuntimeError(f"Error deleting issued credential: {e}")
        logger.info(f"Deleted issued credential: {said}")

    @staticmethod
    def get_tel_events(credential_said: str) -> list:
        """
        Retrieve all TEL events for a specific credential

        Args:
            credential_said: Self-addressing identifier of the credential

        Returns:
            List of TELEvent documents ordered by sequence number
        """
        try:
            return list(
                TELEvent.objects(credential_said=credential_said).order_by("sn")
            )
        except Exception as e:
            raise RuntimeError(f"An error occurred while querying TEL events: {e}")

    def get_credential_stream(self, said: str) -> bytearray:
        """
        Get ACDC + TEL stream for distribution

        Args:
            said: Self-addressing identifier of the credential

        Returns:
            Bytearray containing ACDC credential and all TEL events with attachments
        """
        ims = bytearray()

        # 1. Get credential from MongoDB
        credential = self.get_credential(said)
        if not credential:
            raise NotFoundError(f"Credential not in MongoDB: {said}")

        # 2. Serialize ACDC credential
        serder = serdering.SerderACDC(sad=credential.sad)
        ims.extend(serder.raw)

        anc = credential.anc
        if anc is not None:
            ims.extend(
                core.Counter(
                    core.Codens.SealSourceTriples, count=1, gvrsn=kering.Vrsn_1_0
                ).qb64b
            )
            ims.extend(coring.Prefixer(qb64=anc.prefix).qb64b)
            ims.extend(coring.Seqner(sn=anc.sn).qb64b)
            ims.extend(coring.Saider(qb64=anc.said).qb64b)

        # 3. Get and serialize TEL events with attachments
        tel_events = self.get_tel_events(serder.sad.get("ri"))
        tel_events.extend(self.get_tel_events(said))

        for event in tel_events:
            atc = bytearray()
            serder = serdering.SerderKERI(sad=event.sad)
            ims.extend(serder.raw)

            # Add anchor
            anc = event.anc
            if anc is not None:
                seqner = coring.Seqner(sn=anc.sn)
                saider = coring.Saider(qb64b=anc.said)
                couple = seqner.qb64b + saider.qb64b
                atc.extend(
                    core.Counter(
                        core.Codens.SealSourceCouples, count=1, gvrsn=kering.Vrsn_1_0
                    ).qb64b
                )
                atc.extend(couple)

            # Add datetime stamp
            dts = coring.Dater(dts=event.dts)
            atc.extend(
                core.Counter(
                    code=core.Codens.FirstSeenReplayCouples,
                    count=1,
                    gvrsn=kering.Vrsn_1_0,
                ).qb64b
            )
            atc.extend(core.Number(num=0, code=core.NumDex.Huge).qb64b)
            atc.extend(dts.qb64b)

            # Prepend attachment group counter
            if len(atc) % 4:
                raise ValueError(
                    f"Invalid attachments size={len(atc)}, nonintegral quadlets"
                )

            pcnt = core.Counter(
                code=core.Codens.AttachmentGroup,
                count=(len(atc) // 4),
                gvrsn=kering.Vrsn_1_0,
            ).qb64b
            ims.extend(pcnt)
            ims.extend(atc)

        return ims

    def capture_tel_events(self, issuer: str, regi: str, said: str):
        """
        Capture TEL events for a credential from reger to MongoDB

        Parameters:
            issuer: KERI prefix of the issuer
            said: Self-addressing identifier of the credential
            regi: KERI prefix of the reger
        """
        # Iterate through TEL events (similar to getFelItemPreIter for KEL)
        # Note: May need to adjust method name based on actual Reger API
        try:
            vcp = bytearray(self.reger.cloneTvtAt(regi, sn=0))
            iserder = serdering.SerderKERI(raw=vcp)
            self.serialize_tel_event(issuer, iserder)

            for msg in self.reger.clonePreIter(pre=said):
                iserder = serdering.SerderKERI(raw=bytearray(msg))
                self.serialize_tel_event(issuer, iserder)

        except Exception as e:
            logger.warning(f"Error capturing TEL events for {said}: {e}")
            # Continue even if there are no TEL events or error occurs

    def serialize_tel_event(
        self, prefix: str, serder: serdering.SerderKERI
    ) -> TELEvent:
        """
        Serialize TEL event from KERIpy format to MongoDB

        Args:
            prefix (str): KERI prefix of the issuer
            serder (SerderKERI): TEL event serder

        Returns:
            The serialized TELEvent document
        """

        # 1. Get event from reger
        event_said = serder.said
        credential_said = serder.pre

        # 2. Skip if already exists
        if TELEvent.objects(said=event_said).first():
            return TELEvent.objects.get(said=event_said)

        # 3. Build event data
        event_data = {
            "said": event_said,
            "credential_said": credential_said,
            "sad": serder.ked,
            "sn": serder.sn,
        }

        # 4. Add anchor
        dgkey = dbing.dgKey(credential_said, event_said)  # get message
        if couple := self.reger.getAnc(key=dgkey):
            ancb = bytearray(couple)
            seqner = coring.Seqner(qb64b=ancb, strip=True)
            diger = coring.Diger(qb64b=ancb, strip=True)
            event_data["anc"] = TELAnc(prefix=prefix, sn=seqner.sn, said=diger.qb64)

        # 5. Add datetime stamp
        if dts := serder.ked.get("dt"):
            event_data["dts"] = helping.toIso8601(
                coring.Dater(dts=dts.encode("utf-8")).datetime
            )
        else:
            event_data["dts"] = helping.nowIso8601()

        # 9. Save to MongoDB
        tel_event = TELEvent(**event_data)
        tel_event.save()

        logger.info(
            f"Serialized TEL event: {event_said} for credential: {credential_said}"
        )
        return tel_event

    def add_tel_event(self, event_data: dict) -> TELEvent:
        """
        Add a TEL event for a credential

        Args:
            event_data: Dictionary containing TEL event fields:
                - said: Self-addressing identifier of the event
                - credential_said: Reference to the credential
                - sad: Serialized event data
                - sn: Sequence number
                - sigs: Controller signatures (optional)
                - wigs: Witness signatures (optional)
                - cigs: Signature cigars (optional)
                - tsgs: Timestamp signatures (optional)
                - dts: Datetime stamp

        Returns:
            The created TELEvent document

        Raises:
            ValidationError: If event data is invalid
            NotFoundError: If credential does not exist
        """
        # Validate required fields
        required_fields = ["said", "credential_said", "sad", "sn", "dts"]
        for field in required_fields:
            if field not in event_data:
                raise ValidationError(f"Missing required field: {field}")

        # Validate credential exists
        credential_said = event_data["credential_said"]
        credential = self.get_credential(credential_said)
        if not credential:
            raise NotFoundError(f"Credential not found: {credential_said}")

        # Check if event already exists
        if TELEvent.objects(said=event_data["said"]).first():
            logger.info(f"TEL event already exists: {event_data['said']}")
            return TELEvent.objects.get(said=event_data["said"])

        try:
            # Process embedded documents if present
            tel_event = TELEvent(**event_data)
            tel_event.save()
            logger.info(
                f"Added TEL event: {tel_event.said} for credential: {credential_said}"
            )
            return tel_event
        except Exception as e:
            raise RuntimeError(f"An error occurred while saving TEL event: {e}")
