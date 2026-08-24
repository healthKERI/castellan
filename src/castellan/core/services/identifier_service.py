# -*- encoding: utf-8 -*-
"""
castellan.core.services.identifier_service module

Service and MongoDB document model for castellan-uploaded identifiers.

Each whisper user uploads exactly one non-group identifier during initialization.
Castellan stores these so that all whisper instances can discover peers and
exchange OOBIs before constructing a group multisig.
"""

from dataclasses import asdict
from datetime import datetime

from keri import kering
from keri.help import ogler
from keri.app import habbing
from mongoengine import DateTimeField, Document, StringField, DoesNotExist

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


class UploadedIdentifier(Document):
    """A single non-group KERI identifier uploaded by a whisper instance."""

    aid = StringField(required=True, primary_key=True)  # KERI AID prefix
    alias = StringField(
        required=True, unique=True
    )  # human-readable alias (unique across castellan)
    oobi = StringField(default="")  # OOBI URL for peer resolution
    created_at = DateTimeField(default=datetime.now)

    meta = {
        "indexes": ["alias"],
        "ordering": ["created_at"],
    }


class IdentifierService:
    """Service for storing and retrieving castellan-uploaded identifiers."""

    def __init__(
        self, kelSvc=None, parser=None, kvy=None, hby=None, castellan_hab=None
    ):
        self.kelSvc = kelSvc
        self.parser = parser
        self.kvy = kvy
        self.hby = hby
        self.castellan_hab = castellan_hab

    def upload(
        self, aid: str, alias: str, kel: bytes, oobi: str = ""
    ) -> "UploadedIdentifier":
        """
        Store an identifier uploaded by a whisper instance.

        Args:
            aid:   KERI AID prefix (primary key).
            alias: Human-readable alias — must be unique across castellan.
            kel:   Raw CESR-encoded KEL bytes for the identifier.
            oobi:  OOBI URL for peer resolution (optional).

        Returns:
            The created UploadedIdentifier document.

        Raises:
            ConflictError: If the alias is already in use.
            ValueError: If the KEL cannot be parsed or verified.
        """
        if not aid:
            raise ValueError("aid is required")
        if not alias:
            raise ValueError("alias is required")
        if not kel:
            raise ValueError("kel is required")

        if self.parser is None or self.kvy is None:
            raise RuntimeError(
                "IdentifierService requires parser and kvy to process KEL"
            )

        try:
            self.parser.parse(ims=bytearray(kel), kvy=self.kvy, local=False)
        except Exception as e:
            raise RuntimeError(f"An error occurred parsing KEL into Kevery: {e}")

        if aid not in self.kvy.kevers:
            raise ValueError(
                f"KEL parsed but AID {aid} not found in kevers — KEL may be incomplete or unverifiable"
            )

        if self.kelSvc is not None:
            try:
                self.kelSvc.capture_kel(aid)
                self.kelSvc.scan_for_delegates(aid)
                self.kelSvc.capture_rpys(aid)

                logger.info(f"KEL captured for aid={aid}")
                if self.hby is not None and self.castellan_hab is not None:
                    group_hab = self.hby.habs.get(aid)
                    if group_hab is not None and isinstance(
                        group_hab, habbing.GroupHab
                    ):
                        role_msgs = group_hab.makeEndRole(
                            eid=self.castellan_hab.pre, role=kering.Roles.mailbox
                        )
                        self.parser.parse(ims=bytearray(role_msgs))
                        logger.info(
                            f"Registered castellan as mailbox for group AID={aid}"
                        )
            except Exception as e:
                raise RuntimeError(f"KEL capture failed for aid={aid}: {e}")

        if (identifier := UploadedIdentifier.objects(alias=alias).first()) is None:
            identifier = UploadedIdentifier(aid=aid, alias=alias, oobi=oobi)
            identifier.save()

        logger.info(f"Uploaded identifier aid={aid} alias={alias}")

        return identifier

    def list_all(self) -> list["UploadedIdentifier"]:
        """Return all uploaded identifiers ordered by creation time."""
        return list(UploadedIdentifier.objects.order_by("created_at"))

    def get(self, aid: str) -> "UploadedIdentifier":
        """Fetch a single identifier by AID. Raises NotFoundError if missing."""
        try:
            return UploadedIdentifier.objects.get(aid=aid)
        except DoesNotExist:
            raise NotFoundError(f"Identifier not found: {aid}")

    def get_kel_stream(self, aid: str) -> bytes:
        """
        Return the CESR-encoded KEL stream for the given AID.

        Raises NotFoundError if no identifier exists for aid.
        Returns empty bytes if the KEL has not been captured yet.
        """
        self.get(aid)  # raises NotFoundError if unknown
        if self.kelSvc is None:
            return b""
        try:
            return self.kelSvc.get_kel_stream(aid)
        except Exception as e:
            logger.warning(f"KEL stream retrieval failed for aid={aid}: {e}")
            return b""

    def delete(self, aid: str) -> None:
        """Delete an uploaded identifier. Raises NotFoundError if missing."""
        identifier = self.get(aid)
        identifier.delete()
        logger.info(f"Deleted identifier aid={aid}")

    def get_identifier_with_key_state(self, aid):
        """Retrieves an Identifier by its aid."""
        try:
            identifier = UploadedIdentifier.objects.get(aid=aid)
            key_state = asdict(self.kelSvc.get_keystate(identifier.aid))

            return {
                "alias": identifier.alias,
                "aid": identifier.aid,
                "key_state": key_state,
            }
        except DoesNotExist:
            raise NotFoundError(f"Identifier not found: {aid}")

        except Exception as e:
            if isinstance(e, (ConflictError, NotFoundError)):
                raise
            raise RuntimeError(
                f"An error occurred while querying identifier: {type(e)}"
            )
