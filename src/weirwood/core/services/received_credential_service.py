# -*- encoding: utf-8 -*-
"""
weirwood.core.services.received_credential_service module

Service and MongoDB document model for credentials received by this account.
"""
import math
from datetime import datetime

from keri.app.habbing import Habery
from keri.core import coring, serdering
from keri.help import ogler
from mongoengine import (
    DateTimeField, DictField, Document, Q, StringField
)

from weirwood.core.services.custom.custom_errors import (
    ConflictError, NotFoundError, ValidationError
)
from weirwood.core.services.issued_credential_service import flatten_values

logger = ogler.getLogger()


class ReceivedCredential(Document):
    """ACDC credential received by this account from an external issuer."""
    said = StringField(required=True, primary_key=True)
    sad = DictField(required=True)
    issuer = StringField(required=True)       # external issuer AID
    schema = DictField(required=True)
    holder = StringField(required=True)       # account AID (us)
    status = StringField()                    # "valid" | "revoked"
    search_text = StringField(db_field="_search_text")
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)


class ReceivedCredentialService:
    """Service for managing credentials received by this account."""

    def __init__(self, hby: Habery, rgy, tvy, parser):
        self.hby = hby
        self.rgy = rgy
        self.tvy = tvy
        self.parser = parser
        self.reger = rgy.reger

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def list_credentials(self, filter=None, issuer=None, holder=None,
                          status=None, page=0, page_size=20, order=None):
        """
        Return a page of ReceivedCredential documents matching the given filters.

        Args:
            filter: Case-insensitive string searched across all document fields
                    and all sad dict values (via _search_text).
            issuer: Exact match on issuer AID.
            holder: Exact match on holder AID.
            status: Exact match on status string.
            page: Zero-indexed page number.
            page_size: Number of results per page (default 20).
            order: MongoEngine order_by string or list of strings.

        Returns:
            (credentials_list, total_count, num_pages)
        """
        qs = ReceivedCredential.objects()

        if issuer is not None:
            qs = qs.filter(issuer=issuer)
        if holder is not None:
            qs = qs.filter(holder=holder)
        if status is not None:
            qs = qs.filter(status=status)

        if filter:
            qs = qs.filter(
                Q(said__icontains=filter) |
                Q(issuer__icontains=filter) |
                Q(holder__icontains=filter) |
                Q(status__icontains=filter) |
                Q(search_text__icontains=filter)
            )

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
        """Fetch a single ReceivedCredential by SAID. Raises NotFoundError if missing."""
        try:
            cred = ReceivedCredential.objects.get(said=said)
        except ReceivedCredential.DoesNotExist:
            raise NotFoundError(f"Received credential not found: {said}")
        except Exception as e:
            raise RuntimeError(f"Error querying received credential: {e}")
        return cred

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def save_credential(self, doc: dict, acdc: bytes):
        """
        Parse an ACDC stream and persist a ReceivedCredential record.

        Args:
            doc: Metadata dict with keys: said, issuer, holder, schema,
                 status (optional).
            acdc: Raw ACDC bytes to parse into Regery/Tevery.

        Returns:
            The created ReceivedCredential document.

        Raises:
            ValidationError: If required fields are missing.
            ConflictError: If a record with the same SAID already exists.
            RuntimeError: If ACDC parsing fails.
        """
        said = doc.get("said")
        if not said:
            raise ValidationError("Missing required field: said")

        holder = doc.get("holder")
        if not holder:
            raise ValidationError("Missing required field: holder")

        if ReceivedCredential.objects(said=said).first():
            raise ConflictError(f"Received credential already exists: {said}")

        try:
            self.parser.parse(ims=bytearray(acdc), tvy=self.tvy, local=False)
        except Exception as e:
            raise RuntimeError(f"Error parsing ACDC stream: {e}")

        creder = self.reger.creds.get(keys=(said,))
        if creder is None:
            raise RuntimeError(f"Credential {said} not found in reger after parsing")

        return self._capture(creder, doc)

    def _capture(self, creder, doc: dict):
        """Build and persist a ReceivedCredential from a parsed SerderACDC."""
        status_text = "valid"
        try:
            regk = creder.regi
            vc_state = self.rgy.tevers[regk].vcState(creder.said)
            if vc_state.et in [coring.Ilks.rev, coring.Ilks.brv]:
                status_text = "revoked"
        except Exception:
            pass

        search_text = flatten_values(creder.sad)

        cred = ReceivedCredential(
            said=creder.said,
            sad=creder.sad,
            issuer=creder.issuer,
            schema=doc.get("schema", {}),
            holder=doc.get("holder", creder.issuee or ""),
            status=status_text,
            search_text=search_text,
        )
        cred.save()
        logger.info(f"Saved received credential: {creder.said}")
        return cred

    def update_credential(self, said: str, update_data: dict):
        """
        Update allowed fields on a ReceivedCredential.

        Allowed fields: status, holder.
        """
        cred = self.get_credential(said)
        try:
            for field in ("status", "holder"):
                if field in update_data:
                    setattr(cred, field, update_data[field])
            cred.updated_at = datetime.now()
            cred.save()
        except Exception as e:
            raise RuntimeError(f"Error updating received credential: {e}")
        logger.info(f"Updated received credential: {said}")
        return cred

    def delete_credential(self, said: str):
        """Delete a ReceivedCredential. Raises NotFoundError if missing."""
        cred = self.get_credential(said)
        try:
            cred.delete()
        except Exception as e:
            raise RuntimeError(f"Error deleting received credential: {e}")
        logger.info(f"Deleted received credential: {said}")

    def get_credential_stream(self, said: str) -> bytearray:
        """Return raw ACDC bytes for the given SAID (for stream=true requests)."""
        if said not in self.tvy.tevers:
            raise NotFoundError(f"Credential not in tevers: {said}")

        cred = self.get_credential(said)
        ims = bytearray()
        serder = serdering.SerderKERI(sad=cred.sad)
        ims.extend(serder.raw)
        return ims