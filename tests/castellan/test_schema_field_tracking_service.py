# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.schema_field_tracking_service import (
    SchemaFieldTrackingService,
    TrackedField,
)


class TestTrackFields:
    """Test suite for track_fields method"""

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_track_fields_creates_new_tracking(self, mock_tracking_cls):
        """Test that track_fields creates a new tracking document for a new schema"""
        mock_tracking_cls.objects.return_value.first.return_value = None
        mock_tracking = Mock()
        mock_tracking.fields = []
        mock_tracking_cls.return_value = mock_tracking

        # Create mock dynamic fields
        field1 = Mock()
        field1.__class__.__name__ = "PhoneField"
        field1.label = "Mobile Phone"

        field2 = Mock()
        field2.__class__.__name__ = "EmailFieldValue"
        field2.label = "Work Email"

        SchemaFieldTrackingService.track_fields("ESCHEMA123", [field1, field2])

        mock_tracking_cls.objects.assert_called_once_with(schema_said="ESCHEMA123")
        mock_tracking_cls.assert_called_once_with(schema_said="ESCHEMA123")
        assert len(mock_tracking.fields) == 2
        mock_tracking.save.assert_called_once()

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_track_fields_deduplicates(self, mock_tracking_cls):
        """Test that track_fields doesn't duplicate existing field type/label pairs"""
        existing_field = Mock()
        existing_field.type = "phone"
        existing_field.label = "Mobile Phone"

        mock_tracking = Mock()
        mock_tracking.fields = [existing_field]
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        # Create mock dynamic field with same type/label
        field1 = Mock()
        field1.__class__.__name__ = "PhoneField"
        field1.label = "Mobile Phone"

        SchemaFieldTrackingService.track_fields("ESCHEMA123", [field1])

        # Should not add a duplicate or call save
        assert len(mock_tracking.fields) == 1
        mock_tracking.save.assert_not_called()

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_track_fields_adds_new_to_existing(self, mock_tracking_cls):
        """Test that track_fields adds new fields to existing tracking document"""
        existing_field = Mock()
        existing_field.type = "phone"
        existing_field.label = "Mobile Phone"

        mock_tracking = Mock()
        mock_tracking.fields = [existing_field]
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        # Create mock dynamic field with different type/label
        field1 = Mock()
        field1.__class__.__name__ = "EmailFieldValue"
        field1.label = "Work Email"

        SchemaFieldTrackingService.track_fields("ESCHEMA123", [field1])

        # Should add the new field and save
        assert len(mock_tracking.fields) == 2
        mock_tracking.save.assert_called_once()

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_track_fields_normalizes_field_types(self, mock_tracking_cls):
        """Test that field type names are properly normalized"""
        mock_tracking_cls.objects.return_value.first.return_value = None
        mock_tracking = Mock()
        mock_tracking.fields = []
        mock_tracking_cls.return_value = mock_tracking

        # Create mock dynamic fields with various class names
        test_cases = [
            ("PhoneField", "phone"),
            ("EmailFieldValue", "email"),
            ("DateFieldValue", "date"),
            ("AddressField", "address"),
            ("UrlField", "url"),
            ("TextField", "text"),
        ]

        for class_name, expected_type in test_cases:
            field = Mock()
            field.__class__.__name__ = class_name
            field.label = "Test Label"

            SchemaFieldTrackingService.track_fields("ESCHEMA123", [field])

            # Reset for next iteration
            mock_tracking.fields = []
            mock_tracking_cls.objects.return_value.first.return_value = None
            mock_tracking_cls.return_value = mock_tracking


class TestGetTrackedFields:
    """Test suite for get_tracked_fields method"""

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_get_tracked_fields_returns_fields(self, mock_tracking_cls):
        """Test that get_tracked_fields returns list of tracked fields"""
        field1 = Mock()
        field1.type = "phone"
        field1.label = "Mobile Phone"

        field2 = Mock()
        field2.type = "email"
        field2.label = "Work Email"

        mock_tracking = Mock()
        mock_tracking.fields = [field1, field2]
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        result = SchemaFieldTrackingService.get_tracked_fields("ESCHEMA123")

        assert result == [field1, field2]
        mock_tracking_cls.objects.assert_called_once_with(schema_said="ESCHEMA123")

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_get_tracked_fields_returns_empty_for_unknown_schema(
        self, mock_tracking_cls
    ):
        """Test that get_tracked_fields returns empty list for unknown schema"""
        mock_tracking_cls.objects.return_value.first.return_value = None

        result = SchemaFieldTrackingService.get_tracked_fields("UNKNOWN")

        assert result == []


class TestDeleteTrackedField:
    """Test suite for delete_tracked_field method"""

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_delete_tracked_field_removes_field(self, mock_tracking_cls):
        """Test that delete_tracked_field removes the specified field"""
        field1 = Mock()
        field1.type = "phone"
        field1.label = "Mobile Phone"

        field2 = Mock()
        field2.type = "email"
        field2.label = "Work Email"

        mock_tracking = Mock()
        mock_tracking.fields = [field1, field2]
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        SchemaFieldTrackingService.delete_tracked_field(
            "ESCHEMA123", "phone", "Mobile Phone"
        )

        # Should remove field1, leaving only field2
        assert len(mock_tracking.fields) == 1
        assert mock_tracking.fields[0] == field2
        mock_tracking.save.assert_called_once()

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_delete_tracked_field_raises_not_found_for_unknown_schema(
        self, mock_tracking_cls
    ):
        """Test that delete_tracked_field raises NotFoundError for unknown schema"""
        mock_tracking_cls.objects.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="No tracked fields for schema"):
            SchemaFieldTrackingService.delete_tracked_field(
                "UNKNOWN", "phone", "Mobile Phone"
            )

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_delete_tracked_field_raises_not_found_for_unknown_field(
        self, mock_tracking_cls
    ):
        """Test that delete_tracked_field raises NotFoundError for unknown field"""
        field1 = Mock()
        field1.type = "email"
        field1.label = "Work Email"

        mock_tracking = Mock()
        mock_tracking.fields = [field1]
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        with pytest.raises(NotFoundError, match="Field not found"):
            SchemaFieldTrackingService.delete_tracked_field(
                "ESCHEMA123", "phone", "Mobile Phone"
            )

        # Should not save if field not found
        mock_tracking.save.assert_not_called()


class TestDeleteAllTrackedFields:
    """Test suite for delete_all_tracked_fields method"""

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_delete_all_tracked_fields_deletes_document(self, mock_tracking_cls):
        """Test that delete_all_tracked_fields deletes the tracking document"""
        mock_tracking = Mock()
        mock_tracking_cls.objects.return_value.first.return_value = mock_tracking

        SchemaFieldTrackingService.delete_all_tracked_fields("ESCHEMA123")

        mock_tracking_cls.objects.assert_called_once_with(schema_said="ESCHEMA123")
        mock_tracking.delete.assert_called_once()

    @patch("castellan.core.services.schema_field_tracking_service.SchemaFieldTracking")
    def test_delete_all_tracked_fields_raises_not_found_for_unknown_schema(
        self, mock_tracking_cls
    ):
        """Test that delete_all_tracked_fields raises NotFoundError for unknown schema"""
        mock_tracking_cls.objects.return_value.first.return_value = None

        with pytest.raises(NotFoundError, match="No tracked fields for schema"):
            SchemaFieldTrackingService.delete_all_tracked_fields("UNKNOWN")


class TestTrackedField:
    """Test suite for TrackedField embedded document"""

    def test_to_dict_returns_correct_format(self):
        """Test that TrackedField.to_dict returns correct dictionary"""
        field = TrackedField(type="phone", label="Mobile Phone")
        result = field.to_dict()

        assert result == {"type": "phone", "label": "Mobile Phone"}
