# -*- encoding: utf-8 -*-
"""Tests for dynamic fields functionality."""

import pytest
from datetime import date
from mongoengine import ValidationError

from castellan.core.services.dynamic_fields import (
    PhoneField,
    AddressField,
    DateFieldValue,
    UrlField,
    EmailFieldValue,
    TextField,
    create_dynamic_field,
)


class TestDynamicFieldCreation:
    """Test dynamic field instantiation and validation."""

    def test_phone_field_creation(self):
        field = PhoneField(label="Mobile", value="+1-555-0123")
        assert field.label == "Mobile"
        assert field.value == "+1-555-0123"
        assert field.to_dict() == {
            "type": "phone",
            "label": "Mobile",
            "value": "+1-555-0123",
        }

    def test_email_field_validation(self):
        # Valid email
        field = EmailFieldValue(label="Work Email", value="user@example.com")
        field.validate()

        # Invalid email raises on validation
        with pytest.raises(ValidationError):
            bad_field = EmailFieldValue(label="Bad Email", value="not-an-email")
            bad_field.validate()

    def test_url_field_validation(self):
        # Valid URL
        field = UrlField(label="Website", value="https://example.com")
        field.validate()

        # Invalid URL raises on validation
        with pytest.raises(ValidationError):
            bad_field = UrlField(label="Bad URL", value="not a url")
            bad_field.validate()

    def test_date_field_serialization(self):
        field = DateFieldValue(label="Birth Date", value=date(1990, 1, 15))
        result = field.to_dict()
        assert result["type"] == "date"
        assert result["label"] == "Birth Date"
        assert result["value"] == "1990-01-15"

    def test_text_field_max_length(self):
        # Accepts text up to 2000 chars
        long_text = "x" * 2000
        field = TextField(label="Notes", value=long_text)
        field.validate()

        # Raises if exceeds max_length
        with pytest.raises(ValidationError):
            too_long = "x" * 2001
            bad_field = TextField(label="Notes", value=too_long)
            bad_field.validate()

    def test_address_field(self):
        addr = "123 Main St, Apt 4B, Springfield, IL 62701"
        field = AddressField(label="Home Address", value=addr)
        assert field.to_dict()["type"] == "address"
        assert addr in field.get_value_for_search()


class TestDynamicFieldFactory:
    """Test factory function for creating fields from API input."""

    def test_create_phone_field(self):
        data = {"type": "phone", "label": "Mobile", "value": "+1-555-0123"}
        field = create_dynamic_field(data)
        assert isinstance(field, PhoneField)
        assert field.label == "Mobile"

    def test_create_email_field(self):
        data = {"type": "email", "label": "Email", "value": "test@example.com"}
        field = create_dynamic_field(data)
        assert isinstance(field, EmailFieldValue)

    def test_invalid_type_raises(self):
        data = {"type": "invalid", "label": "Test", "value": "value"}
        with pytest.raises(ValueError, match="Invalid field type"):
            create_dynamic_field(data)

    def test_missing_required_fields_raises(self):
        # Missing value
        with pytest.raises(ValueError, match="must include type, label, and value"):
            create_dynamic_field({"type": "text", "label": "Test"})

    def test_create_all_types(self):
        """Verify all field types can be created."""
        test_cases = [
            ("phone", "+1234567890"),
            ("address", "123 Main St"),
            ("date", "2024-01-15"),
            ("url", "https://example.com"),
            ("email", "test@example.com"),
            ("text", "Some text"),
        ]

        for field_type, value in test_cases:
            data = {"type": field_type, "label": "Test", "value": value}
            field = create_dynamic_field(data)
            assert field.label == "Test"


class TestSearchTextExtraction:
    """Test get_value_for_search() methods."""

    def test_phone_field_search_text(self):
        field = PhoneField(label="Mobile", value="+1-555-0123")
        search_text = field.get_value_for_search()
        assert "Mobile" in search_text
        assert "+1-555-0123" in search_text

    def test_all_fields_include_label_and_value(self):
        fields = [
            PhoneField(label="Phone", value="123456"),
            AddressField(label="Address", value="123 Main"),
            TextField(label="Note", value="Important"),
            EmailFieldValue(label="Email", value="a@b.com"),
            UrlField(label="URL", value="https://x.com"),
            DateFieldValue(label="Date", value=date(2024, 1, 1)),
        ]

        for field in fields:
            search = field.get_value_for_search()
            assert field.label in search
