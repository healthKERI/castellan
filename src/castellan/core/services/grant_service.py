# -*- encoding: utf-8 -*-
"""
castellan.core.services.grant_service module

Service and MongoDB document model for grant events.
"""

import math
from datetime import datetime

from keri.core import coring
from keri.help import helping
from mongoengine import (
    Document,
    StringField,
    DictField,
    ListField,
    DateTimeField,
    DoesNotExist,
    Q,
    EmbeddedDocument,
    EmbeddedDocumentField,
)

from castellan.core.services.custom.custom_errors import NotFoundError


class Tsgs(EmbeddedDocument):
    prefix = StringField(required=True)
    seq = StringField(required=True)
    dig = StringField(required=True)
    sigs = ListField(required=False, default=[])


class Scgs(EmbeddedDocument):
    verfer = StringField(required=True)
    cigar = StringField(required=True)


class Grant(Document):
    """Grant event document."""

    said = StringField(required=True, unique=True)  # Self-addressing identifier
    sad = DictField(required=True)  # The grant event data
    cigs = ListField(EmbeddedDocumentField(Scgs))
    tsgs = EmbeddedDocumentField(Tsgs)
    pathed = ListField(StringField(required=False))  # Pathed attachment data
    created_at = DateTimeField(default=datetime.now)

    meta = {
        "indexes": ["said"],
        "ordering": ["-created_at"],
        "collection": "grant",
    }


class GrantService:
    """Service for storing and retrieving grant events."""

    def __init__(self, hby):
        self.hby = hby

    @staticmethod
    def get_grant(said: str) -> Grant:
        """
        Fetch a single grant by its SAID.

        Args:
            said: The grant SAID to look up.

        Returns:
            The Grant document.

        Raises:
            NotFoundError: If no grant exists with the given SAID.
        """
        try:
            return Grant.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Grant not found: {said}")

    @staticmethod
    def list_grants(
        page: int = 0,
        page_size: int = 20,
        filter_term: str | None = None,
        order: list[str] | None = None,
    ) -> tuple[list[Grant], int, int]:
        """
        List grants with pagination, filtering, and sorting.

        Args:
            page: Zero-indexed page number (default 0).
            page_size: Results per page (default 20).
            filter_term: Case-insensitive substring match against said or pathed.
            order: Sort field(s), e.g. ["-created_at"] (default ["-created_at"]).

        Returns:
            (grants, total_count, num_pages)
        """
        qs = Grant.objects()

        if filter_term:
            qs = qs.filter(
                Q(said__icontains=filter_term) | Q(pathed__icontains=filter_term)
            )

        if order:
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        items = list(qs.skip(page * page_size).limit(page_size))
        return items, total, num_pages

    @staticmethod
    def update_grant(
        said: str,
        event: dict | None = None,
        signatures: list[str] | None = None,
        pathed: str | None = None,
    ) -> Grant:
        """
        Update an existing grant.

        Args:
            said: The grant SAID to update.
            event: New event data (optional).
            signatures: New list of signatures (replaces existing, optional).
            pathed: New pathed data (optional).

        Returns:
            The updated Grant document.

        Raises:
            NotFoundError: If no grant exists with the given SAID.
        """
        try:
            grant = Grant.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Grant not found: {said}")

        if event is not None:
            grant.event = event
        if signatures is not None:
            grant.signatures = signatures
        if pathed is not None:
            grant.pathed = pathed

        grant.updated_at = datetime.now()
        grant.save()
        return grant

    @staticmethod
    def add_signature(said: str, signature: str) -> Grant:
        """
        Add a signature to an existing grant.

        Args:
            said: The grant SAID.
            signature: The signature to add.

        Returns:
            The updated Grant document.

        Raises:
            NotFoundError: If no grant exists with the given SAID.
            ValueError: If signature is empty.
        """
        if not signature:
            raise ValueError("signature is required")

        try:
            grant = Grant.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Grant not found: {said}")

        grant.signatures.append(signature)
        grant.updated_at = datetime.now()
        grant.save()
        return grant

    @staticmethod
    def remove_signature(said: str, signature: str) -> Grant:
        """
        Remove a signature from an existing grant.

        Args:
            said: The grant SAID.
            signature: The signature to remove.

        Returns:
            The updated Grant document.

        Raises:
            NotFoundError: If no grant exists with the given SAID,
                          or if the signature is not found.
        """
        try:
            grant = Grant.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Grant not found: {said}")

        if signature not in grant.signatures:
            raise NotFoundError(f"Signature not found in grant: {said}")

        grant.signatures.remove(signature)
        grant.updated_at = datetime.now()
        grant.save()
        return grant

    @staticmethod
    def delete_grant(said: str) -> None:
        """
        Delete a grant.

        Args:
            said: The grant SAID to delete.

        Raises:
            NotFoundError: If no grant exists with the given SAID.
        """
        try:
            grant = Grant.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Grant not found: {said}")

        grant.delete()

    def capture_grant(self, said: str) -> Grant:
        serder = self.hby.db.exns.get(
            keys=(said,),
        )
        if not serder:
            raise ValueError(f"invalid grant said ({said}), not saved")

        if serder.ked.get("r") != "/ipex/grant":
            raise ValueError(f"invalid grant said ({said}), not an IPEX grant")

        tsgs = None
        klases = (coring.Prefixer, coring.Seqner, coring.Saider)
        args = ("qb64", "snh", "qb64")

        for keys, siger in self.hby.db.esigs.getItemIter(keys=(said, "")):
            prefixer, seqner, saider = helping.klasify(
                sers=keys[1:], klases=klases, args=args
            )
            if not tsgs:
                tsgs = Tsgs(
                    prefix=prefixer.qb64, seq=seqner.qb64, dig=saider.qb64, sigs=[]
                )

            tsgs.sigs.append(siger.qb64)

        scgs = []
        cigars = self.hby.db.ecigs.get(keys=(serder.said,))
        for cigar in cigars:
            scgs.append(Scgs(verfer=cigar.verfer.qb64, cigar=cigar.qb64))

        pathed = self.hby.db.epath.get(keys=(serder.said,))

        grant = Grant(
            said=serder.said,
            sad=serder.ked,
            tsgs=tsgs,
            cigs=scgs,
            pathed=pathed,
        )

        grant.save()
        return grant
