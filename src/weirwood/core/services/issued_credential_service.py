# -*- encoding: utf-8 -*-
"""
weirwood.core.services.issued_credential_service module

Service and MongoDB document model for credentials issued by this account.
"""
import math
from datetime import datetime

from keri.app.habbing import Habery
from keri.core import coring, serdering
from keri.help import ogler
from mongoengine import (
    BooleanField, DateTimeField, DictField, Document, Q, StringField
)

from weirwood.core.services.custom.custom_errors import (
    ConflictError, NotFoundError, ValidationError
)

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


class IssuedCredential(Document):
    """ACDC credential issued by this account to a recipient."""
    said = StringField(required=True, primary_key=True)
    sad = DictField(required=True)
    issuer = StringField(required=True)       # account AID (us)
    schema = DictField(required=True)
    recipient = StringField()                 # holder AID
    status = StringField()                    # "issued" | "revoked"
    published = BooleanField(default=False)
    search_text = StringField(db_field="_search_text")  # flattened sad values
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class IssuedCredentialService:
    """Service for managing credentials issued by this account."""

    def __init__(self, hby: Habery, rgy, tvy, parser):
        self.hby = hby
        self.rgy = rgy
        self.tvy = tvy
        self.parser = parser
        self.reger = rgy.reger

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_credentials(self, filter=None, issuer=None, recipient=None,
                          status=None, published=None,
                          page=0, page_size=20, order=None):
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
                Q(said__icontains=filter) |
                Q(issuer__icontains=filter) |
                Q(recipient__icontains=filter) |
                Q(status__icontains=filter) |
                Q(search_text__icontains=filter)
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

    def get_credential(self, said: str):
        """Fetch a single IssuedCredential by SAID. Raises NotFoundError if missing."""
        try:
            cred = IssuedCredential.objects.get(said=said)
        except IssuedCredential.DoesNotExist:
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

        try:
            self.parser.parse(ims=bytearray(acdc), tvy=self.tvy, local=False)
        except Exception as e:
            raise RuntimeError(f"Error parsing ACDC stream: {e}")

        self.tvy.processEscrows()

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

        search_text = flatten_values(creder.sad)

        cred = IssuedCredential(
            said=creder.said,
            sad=creder.sad,
            issuer=creder.issuer,
            schema=doc.get("schema", {}),
            recipient=creder.issuee or doc.get("recipient"),
            status=status_text,
            published=doc.get("publish", False),
            search_text=search_text,
        )
        cred.save()
        logger.info(f"Saved issued credential: {creder.said}")
        return cred

    def update_credential(self, said: str, update_data: dict):
        """
        Update allowed fields on an IssuedCredential.

        Allowed fields: status, published, recipient.
        """
        cred = self.get_credential(said)
        try:
            for field in ("status", "published", "recipient"):
                if field in update_data:
                    setattr(cred, field, update_data[field])
            cred.updated_at = datetime.now()
            cred.save()
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

    def get_credential_stream(self, said: str) -> bytearray:
        """Return raw ACDC bytes for the given SAID (for stream=true requests)."""
        from keri import core, kering

        if said not in self.tvy.tevers:
            raise NotFoundError(f"Credential not in tevers: {said}")

        cred = self.get_credential(said)
        ims = bytearray()
        serder = serdering.SerderKERI(sad=cred.sad)
        ims.extend(serder.raw)
        return ims