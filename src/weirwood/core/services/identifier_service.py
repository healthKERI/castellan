# -*- encoding: utf-8 -*-
"""
weirwood.core.services.identifier_service module

Service and MongoDB document model for weirwood-uploaded identifiers.

Each whisper user uploads exactly one non-group identifier during initialization.
Weirwood stores these so that all whisper instances can discover peers and
exchange OOBIs before constructing a group multisig.
"""
from datetime import datetime

from keri.help import ogler
from mongoengine import DateTimeField, Document, StringField

from weirwood.core.services.custom.custom_errors import ConflictError, NotFoundError

logger = ogler.getLogger()


class UploadedIdentifier(Document):
    """A single non-group KERI identifier uploaded by a whisper instance."""
    aid = StringField(required=True, primary_key=True)   # KERI AID prefix
    alias = StringField(required=True, unique=True)      # human-readable alias (unique across weirwood)
    oobi = StringField(default="")                       # OOBI URL for peer resolution
    created_at = DateTimeField(default=datetime.now)

    meta = {
        "indexes": ["alias"],
        "ordering": ["created_at"],
    }


class IdentifierService:
    """Service for storing and retrieving weirwood-uploaded identifiers."""

    def upload(self, aid: str, alias: str, oobi: str = "") -> "UploadedIdentifier":
        """
        Store an identifier uploaded by a whisper instance.

        Args:
            aid:   KERI AID prefix (primary key).
            alias: Human-readable alias — must be unique across weirwood.
            oobi:  OOBI URL for peer resolution (optional).

        Returns:
            The created UploadedIdentifier document.

        Raises:
            ConflictError: If the alias is already in use.
        """
        if not aid:
            raise ValueError("aid is required")
        if not alias:
            raise ValueError("alias is required")

        if UploadedIdentifier.objects(alias=alias).first() is not None:
            raise ConflictError(f"Alias '{alias}' is already uploaded to weirwood")

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
        except UploadedIdentifier.DoesNotExist:
            raise NotFoundError(f"Identifier not found: {aid}")

    def delete(self, aid: str) -> None:
        """Delete an uploaded identifier. Raises NotFoundError if missing."""
        identifier = self.get(aid)
        identifier.delete()
        logger.info(f"Deleted identifier aid={aid}")