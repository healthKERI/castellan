# -*- encoding: utf-8 -*-
"""
castellan.core.services.registry_service module

Service and MongoDB document model for credential registries.
"""

import math
from datetime import datetime

from mongoengine import (
    Document,
    StringField,
    DateTimeField,
    DoesNotExist,
    Q,
    NotUniqueError,
)

from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError


class Registry(Document):
    """Credential registry document."""

    registry_pre = StringField(required=True, unique=True)  # Registry prefix/identifier
    registry_said = StringField(
        required=True, unique=True
    )  # Self-addressing identifier
    registry_name = StringField(required=True)  # Human-readable name
    issuer_aid = StringField(required=True)  # AID of the issuer
    created_at = DateTimeField(default=datetime.now)

    meta = {
        "indexes": ["registry_pre", "registry_said", "issuer_aid"],
        "ordering": ["-created_at"],
        "collection": "registry",
    }


class RegistryService:
    """Service for storing and retrieving credential registries."""

    @staticmethod
    def create_registry(
        registry_pre: str,
        registry_said: str,
        registry_name: str,
        issuer_aid: str,
    ) -> Registry:
        """
        Create a new credential registry.

        Args:
            registry_pre: Registry prefix/identifier (must be unique).
            registry_said: Self-addressing identifier (must be unique).
            registry_name: Human-readable name for the registry.
            issuer_aid: AID of the issuer.

        Returns:
            The created Registry document.

        Raises:
            ConflictError: If a registry with the same pre or said already exists.
            ValueError: If required fields are missing.
        """
        if not registry_pre:
            raise ValueError("registry_pre is required")
        if not registry_said:
            raise ValueError("registry_said is required")
        if not registry_name:
            raise ValueError("registry_name is required")
        if not issuer_aid:
            raise ValueError("issuer_aid is required")

        try:
            registry = Registry(
                registry_pre=registry_pre,
                registry_said=registry_said,
                registry_name=registry_name,
                issuer_aid=issuer_aid,
            )
            registry.save()
            return registry
        except NotUniqueError:
            raise ConflictError(
                f"Registry with pre '{registry_pre}' or said '{registry_said}' already exists"
            )

    @staticmethod
    def get_registry(registry_pre: str) -> Registry:
        """
        Fetch a single registry by its prefix.

        Args:
            registry_pre: The registry prefix to look up.

        Returns:
            The Registry document.

        Raises:
            NotFoundError: If no registry exists with the given prefix.
        """
        try:
            return Registry.objects.get(registry_pre=registry_pre)
        except DoesNotExist:
            raise NotFoundError(f"Registry not found: {registry_pre}")

    @staticmethod
    def get_registry_by_said(registry_said: str) -> Registry:
        """
        Fetch a single registry by its SAID.

        Args:
            registry_said: The registry SAID to look up.

        Returns:
            The Registry document.

        Raises:
            NotFoundError: If no registry exists with the given SAID.
        """
        try:
            return Registry.objects.get(registry_said=registry_said)
        except DoesNotExist:
            raise NotFoundError(f"Registry not found with said: {registry_said}")

    @staticmethod
    def list_registries(
        page: int = 0,
        page_size: int = 20,
        filter_term: str | None = None,
        order: list[str] | None = None,
        issuer_aid: str | None = None,
    ) -> tuple[list[Registry], int, int]:
        """
        List registries with pagination, filtering, and sorting.

        Args:
            page: Zero-indexed page number (default 0).
            page_size: Results per page (default 20).
            filter_term: Case-insensitive substring match against registry_name, registry_pre, or registry_said.
            order: Sort field(s), e.g. ["-created_at"] (default ["-created_at"]).
            issuer_aid: Filter by issuer AID (optional).

        Returns:
            (registries, total_count, num_pages)
        """
        qs = Registry.objects()

        if issuer_aid:
            qs = qs.filter(issuer_aid=issuer_aid)

        if filter_term:
            qs = qs.filter(
                Q(registry_name__icontains=filter_term)
                | Q(registry_pre__icontains=filter_term)
                | Q(registry_said__icontains=filter_term)
            )

        if order:
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        items = list(qs.skip(page * page_size).limit(page_size))
        return items, total, num_pages

    def update_registry(self, registry_pre: str, update_data: dict) -> Registry:
        """
        Update an existing registry.

        Args:
            registry_pre: The registry prefix to update.
            update_data: Dictionary of fields to update. Only registry_name can be updated.

        Returns:
            The updated Registry document.

        Raises:
            NotFoundError: If no registry exists with the given prefix.
            ValueError: If attempting to update immutable fields.
        """
        registry = self.get_registry(registry_pre)

        # Only allow updating registry_name
        immutable_fields = {"registry_pre", "registry_said", "issuer_aid"}
        attempted_immutable = set(update_data.keys()) & immutable_fields
        if attempted_immutable:
            raise ValueError(
                f"Cannot update immutable fields: {', '.join(attempted_immutable)}"
            )

        if "registry_name" in update_data:
            new_name = update_data["registry_name"]
            if not new_name or not isinstance(new_name, str):
                raise ValueError("registry_name must be a non-empty string")
            registry.registry_name = new_name.strip()

        registry.save()
        return registry

    def delete_registry(self, registry_pre: str) -> None:
        """
        Delete a registry.

        Args:
            registry_pre: The registry prefix to delete.

        Raises:
            NotFoundError: If no registry exists with the given prefix.
        """
        registry = self.get_registry(registry_pre)
        registry.delete()
