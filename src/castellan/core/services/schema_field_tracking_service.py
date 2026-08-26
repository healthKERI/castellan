# -*- encoding: utf-8 -*-
"""
castellan.core.services.schema_field_tracking_service module

Service for tracking dynamic field types/labels used with credential schemas.
"""

from datetime import datetime
from typing import List

from keri.help import ogler
from mongoengine import (
    DateTimeField,
    Document,
    EmbeddedDocument,
    EmbeddedDocumentField,
    ListField,
    StringField,
)

from castellan.core.services.custom.custom_errors import NotFoundError

logger = ogler.getLogger()


class TrackedField(EmbeddedDocument):
    """A tracked dynamic field type/label pair."""

    type = StringField(required=True, max_length=50)
    label = StringField(required=True, max_length=255)

    def to_dict(self):
        return {"type": self.type, "label": self.label}


class SchemaFieldTracking(Document):
    """Tracks unique dynamic field types/labels used with a schema."""

    schema_said = StringField(required=True, primary_key=True)
    fields = ListField(EmbeddedDocumentField(TrackedField), default=list)
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    meta = {"collection": "schema_field_tracking"}


class SchemaFieldTrackingService:
    """Service for tracking dynamic fields used with schemas."""

    @staticmethod
    def track_fields(schema_said: str, dynamic_fields: List):
        """
        Add field type/label pairs from dynamic_fields to tracked set for schema.

        Args:
            schema_said: SAID of the schema
            dynamic_fields: List of DynamicField objects from credential

        Returns:
            Updated or created SchemaFieldTracking document
        """
        # Get or create tracking document
        tracking = SchemaFieldTracking.objects(schema_said=schema_said).first()
        if tracking is None:
            tracking = SchemaFieldTracking(schema_said=schema_said)

        # Build set of existing (type, label) tuples
        existing_fields = {(f.type, f.label) for f in tracking.fields}

        # Add new unique fields
        new_fields = []
        for field in dynamic_fields:
            # Extract field type from class name
            field_type = (
                field.__class__.__name__.replace("Field", "")
                .replace("FieldValue", "")
                .lower()
            )

            # Handle naming inconsistencies
            if field_type == "emailvalue":
                field_type = "email"
            elif field_type == "datevalue":
                field_type = "date"
            elif field_type == "phonevalue":
                field_type = "phone"
            elif field_type == "addressvalue":
                field_type = "address"
            elif field_type == "urlvalue":
                field_type = "url"
            elif field_type == "textvalue":
                field_type = "text"

            pair = (field_type, field.label)
            if pair not in existing_fields:
                new_fields.append(TrackedField(type=field_type, label=field.label))
                existing_fields.add(pair)

        if new_fields:
            tracking.fields.extend(new_fields)
            tracking.updated_at = datetime.now()
            tracking.save()
            logger.info(
                f"Tracked {len(new_fields)} new fields for schema {schema_said}"
            )

        return tracking

    @staticmethod
    def get_tracked_fields(schema_said: str):
        """
        Get all tracked field type/label pairs for a schema.

        Args:
            schema_said: SAID of the schema

        Returns:
            List of TrackedField objects, or empty list if none tracked
        """
        tracking = SchemaFieldTracking.objects(schema_said=schema_said).first()
        if tracking is None:
            return []
        return tracking.fields

    @staticmethod
    def delete_tracked_field(schema_said: str, field_type: str, field_label: str):
        """
        Remove a specific field type/label pair from tracking.

        Args:
            schema_said: SAID of the schema
            field_type: Field type to remove
            field_label: Field label to remove

        Raises:
            NotFoundError: If schema tracking or field not found
        """
        tracking = SchemaFieldTracking.objects(schema_said=schema_said).first()
        if tracking is None:
            raise NotFoundError(f"No tracked fields for schema: {schema_said}")

        # Find and remove the matching field
        initial_count = len(tracking.fields)
        tracking.fields = [
            f
            for f in tracking.fields
            if not (f.type == field_type and f.label == field_label)
        ]

        if len(tracking.fields) == initial_count:
            raise NotFoundError(
                f"Field not found: type={field_type}, label={field_label}"
            )

        tracking.updated_at = datetime.now()
        tracking.save()
        logger.info(
            f"Removed field {field_type}/{field_label} from schema {schema_said}"
        )
        return tracking

    @staticmethod
    def delete_all_tracked_fields(schema_said: str):
        """
        Remove all tracked fields for a schema (delete the tracking document).

        Args:
            schema_said: SAID of the schema

        Raises:
            NotFoundError: If schema tracking not found
        """
        tracking = SchemaFieldTracking.objects(schema_said=schema_said).first()
        if tracking is None:
            raise NotFoundError(f"No tracked fields for schema: {schema_said}")

        tracking.delete()
        logger.info(f"Deleted all tracked fields for schema {schema_said}")
