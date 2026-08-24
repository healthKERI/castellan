# -*- encoding: utf-8 -*-
"""
castellan.core.services.dynamic_fields module

EmbeddedDocument models for dynamic fields on IssuedCredential.
Supports phone, address, date, url, email, and text field types.
"""

from datetime import datetime
from keri.help import ogler

from mongoengine import (
    EmbeddedDocument,
    StringField,
    DateField,
    EmailField,
    URLField,
)

logger = ogler.getLogger()


class DynamicField(EmbeddedDocument):
    """Base class for dynamic credential fields."""

    meta = {
        "allow_inheritance": True,
        "abstract": True,
    }

    label = StringField(required=True, max_length=255)

    def to_dict(self):
        """Serialize to dict for API responses."""
        raise NotImplementedError("Subclasses must implement to_dict()")

    def get_value_for_search(self):
        """Extract value for full-text search indexing."""
        raise NotImplementedError("Subclasses must implement get_value_for_search()")


class PhoneField(DynamicField):
    """Phone number field."""

    value = StringField(required=True, max_length=50)

    def to_dict(self):
        return {"type": "phone", "label": self.label, "value": self.value}

    def get_value_for_search(self):
        return f"{self.label} {self.value}"


class AddressField(DynamicField):
    """Address field."""

    value = StringField(required=True, max_length=500)

    def to_dict(self):
        return {"type": "address", "label": self.label, "value": self.value}

    def get_value_for_search(self):
        return f"{self.label} {self.value}"


class DateFieldValue(DynamicField):
    """Date field with validation."""

    value = DateField(required=True)

    def to_dict(self):
        logger.info(
            f"Converting DateFieldValue to dict with label: {self.label}, value: {self.value}"
        )
        return {
            "type": "date",
            "label": self.label,
            "value": self.value.isoformat() if self.value else None,
        }

    def get_value_for_search(self):
        date_str = self.value.isoformat() if self.value else ""
        return f"{self.label} {date_str}"


class UrlField(DynamicField):
    """URL field with validation."""

    value = URLField(required=True)

    def to_dict(self):
        return {"type": "url", "label": self.label, "value": self.value}

    def get_value_for_search(self):
        return f"{self.label} {self.value}"


class EmailFieldValue(DynamicField):
    """Email field with validation."""

    value = EmailField(required=True)

    def to_dict(self):
        return {"type": "email", "label": self.label, "value": self.value}

    def get_value_for_search(self):
        return f"{self.label} {self.value}"


class TextField(DynamicField):
    """Text field."""

    value = StringField(required=True, max_length=2000)

    def to_dict(self):
        return {"type": "text", "label": self.label, "value": self.value}

    def get_value_for_search(self):
        return f"{self.label} {self.value}"


def create_dynamic_field(field_data: dict) -> DynamicField:
    """
    Factory function to create appropriate DynamicField subclass from API input.

    Args:
        field_data: Dict with keys: type, label, value

    Returns:
        Instance of appropriate DynamicField subclass

    Raises:
        ValueError: If type is invalid or required fields missing
    """
    field_type = field_data.get("type")
    label = field_data.get("label")
    value = field_data.get("value")

    if not field_type or not label or value is None:
        raise ValueError("Field data must include type, label, and value")

    type_map = {
        "phone": PhoneField,
        "address": AddressField,
        "date": DateFieldValue,
        "url": UrlField,
        "email": EmailFieldValue,
        "text": TextField,
    }

    field_class = type_map.get(field_type)
    if not field_class:
        valid_types = ", ".join(type_map.keys())
        raise ValueError(
            f"Invalid field type: {field_type}. Valid types: {valid_types}"
        )

    # Coerce value for date fields to appropriate type
    if field_type == "date":
        date_value = None
        for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"]:
            try:
                date_value = datetime.strptime(value, fmt)
                break

            except ValueError:
                continue

        if date_value is None:
            raise ValueError(f"Invalid date format for value: {value}")

        value = date_value

    return field_class(label=label, value=value)
