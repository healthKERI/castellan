# -*- encoding: utf-8 -*-
"""
castellan.core.services.schema_service module

Service and MongoDB document model for JSON schema documents, keyed by SAID,
so they can be resolved independently of any credential that embeds them
(e.g. via the /oobi/{said} schema OOBI).
"""

from datetime import datetime

from keri.core.scheming import Schemer
from mongoengine import BinaryField, DateTimeField, DynamicField, Document, StringField

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
        except Schema.DoesNotExist:
            raise NotFoundError(f"Schema not found: {said}")
