# -*- encoding: utf-8 -*-
"""
castellan.core.services.schema_service module

Service and MongoDB document model for JSON schema documents, keyed by SAID,
so they can be resolved independently of any credential that embeds them
(e.g. via the /oobi/{said} schema OOBI).
"""

from datetime import datetime

from keri.core.scheming import Schemer
from mongoengine import (
    BinaryField,
    DateTimeField,
    DynamicField,
    Document,
    StringField,
    DoesNotExist,
)

from castellan.core.services.custom.custom_errors import NotFoundError


class Schema(Document):
    """JSON schema document, keyed by its self-addressing identifier (SAID)."""

    said = StringField(required=True, primary_key=True)
    # DynamicField, not DictField: JSON Schema keys ($id, $schema, ...) start
    # with "$", which DictField.validate() rejects unconditionally.
    sed = DynamicField(required=True)
    raw = BinaryField(required=True)
    created_at = DateTimeField(default=datetime.now)


class SchemaService:
    """Service for persisting and resolving JSON schema documents."""

    def save_schema(self, sed: dict) -> Schema:
        """
        Derive and verify the SAID of the given schema dict via keri's Schemer,
        then persist it. Idempotent — a second call with the same sed returns
        the existing document without re-saving.
        """
        schemer = Schemer(sed=sed)

        existing = Schema.objects(said=schemer.said).first()
        if existing is not None:
            return existing

        schema = Schema(said=schemer.said, sed=schemer.sed, raw=schemer.raw)
        schema.save()
        return schema

    def get_schema(self, said: str) -> Schema:
        """Fetch a single Schema by SAID. Raises NotFoundError if missing."""
        try:
            return Schema.objects.get(said=said)
        except DoesNotExist:
            raise NotFoundError(f"Schema not found: {said}")

    def list_schemas(self, page=0, page_size=20, order=None):
        """
        List all schemas with pagination.

        Args:
            page: Zero-indexed page number (default 0)
            page_size: Results per page (default 20)
            order: Sort field(s), e.g., ["-created_at", "said"] (default ["-created_at"])

        Returns:
            tuple: (schemas, total_count, num_pages)
        """
        import math

        qs = Schema.objects()

        # Ordering
        if order:
            if isinstance(order, str):
                order = [order]
            qs = qs.order_by(*order)
        else:
            qs = qs.order_by("-created_at")

        # Pagination
        total = qs.count()
        num_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
        schemas = list(qs.skip(page * page_size).limit(page_size))

        return schemas, total, num_pages

    def delete_schema(self, said: str):
        """
        Delete a schema by SAID.

        Args:
            said: The schema SAID to delete

        Raises:
            NotFoundError: If schema doesn't exist
        """
        schema = self.get_schema(said)  # Ensures exists, raises NotFoundError
        try:
            schema.delete()
        except Exception as e:
            raise RuntimeError(f"Error deleting schema: {e}")
