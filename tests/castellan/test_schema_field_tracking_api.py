# -*- encoding: utf-8 -*-
from unittest.mock import Mock

import falcon
import pytest

from castellan.app.api.schema_field_tracking import SchemaFieldTrackingEnd
from castellan.core.services.custom.custom_errors import NotFoundError


class TestSchemaFieldTrackingGet:
    """Test suite for GET /schemas/{said}/fields"""

    def setup_method(self):
        self.service = Mock()
        self.end = SchemaFieldTrackingEnd(self.service)
        self.req = Mock()
        self.resp = Mock()

    def test_on_get_returns_tracked_fields(self):
        """Test GET returns tracked fields for a schema"""
        field1 = Mock()
        field1.type = "phone"
        field1.label = "Mobile Phone"

        field2 = Mock()
        field2.type = "email"
        field2.label = "Work Email"

        self.service.get_tracked_fields.return_value = [field1, field2]

        self.end.on_get(self.req, self.resp, "ESCHEMA123")

        assert self.resp.status == falcon.HTTP_200
        assert self.resp.content_type == "application/json"
        assert self.resp.media == {
            "schema_said": "ESCHEMA123",
            "fields": [
                {"type": "phone", "label": "Mobile Phone"},
                {"type": "email", "label": "Work Email"},
            ],
        }
        self.service.get_tracked_fields.assert_called_once_with("ESCHEMA123")

    def test_on_get_returns_empty_list_for_new_schema(self):
        """Test GET returns empty list for schema with no tracked fields"""
        self.service.get_tracked_fields.return_value = []

        self.end.on_get(self.req, self.resp, "ESCHEMA456")

        assert self.resp.status == falcon.HTTP_200
        assert self.resp.content_type == "application/json"
        assert self.resp.media == {"schema_said": "ESCHEMA456", "fields": []}
        self.service.get_tracked_fields.assert_called_once_with("ESCHEMA456")

    def test_on_get_handles_service_error(self):
        """Test GET handles service errors"""
        self.service.get_tracked_fields.side_effect = Exception("Database error")

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_get(self.req, self.resp, "ESCHEMA123")


class TestSchemaFieldTrackingDelete:
    """Test suite for DELETE /schemas/{said}/fields"""

    def setup_method(self):
        self.service = Mock()
        self.end = SchemaFieldTrackingEnd(self.service)
        self.req = Mock()
        self.resp = Mock()

    def test_on_delete_removes_field_successfully(self):
        """Test DELETE with type and label removes field"""
        self.req.get_param.side_effect = lambda k: (
            "phone" if k == "type" else "Mobile Phone" if k == "label" else None
        )

        self.end.on_delete(self.req, self.resp, "ESCHEMA123")

        assert self.resp.status == falcon.HTTP_204
        self.service.delete_tracked_field.assert_called_once_with(
            "ESCHEMA123", "phone", "Mobile Phone"
        )

    def test_on_delete_returns_400_when_type_missing(self):
        """Test DELETE returns 400 when type parameter is missing"""
        self.req.get_param.side_effect = lambda k: (
            None if k == "type" else "Mobile Phone" if k == "label" else None
        )

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_delete(self.req, self.resp, "ESCHEMA123")

        self.service.delete_tracked_field.assert_not_called()

    def test_on_delete_returns_400_when_label_missing(self):
        """Test DELETE returns 400 when label parameter is missing"""
        self.req.get_param.side_effect = lambda k: (
            "phone" if k == "type" else None if k == "label" else None
        )

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_delete(self.req, self.resp, "ESCHEMA123")

        self.service.delete_tracked_field.assert_not_called()

    def test_on_delete_returns_400_when_both_params_missing(self):
        """Test DELETE returns 400 when both parameters are missing"""
        self.req.get_param.return_value = None

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_delete(self.req, self.resp, "ESCHEMA123")

        self.service.delete_tracked_field.assert_not_called()

    def test_on_delete_returns_404_for_non_existent_schema(self):
        """Test DELETE returns 404 when schema tracking doesn't exist"""
        self.req.get_param.side_effect = lambda k: (
            "phone" if k == "type" else "Mobile Phone" if k == "label" else None
        )
        self.service.delete_tracked_field.side_effect = NotFoundError(
            "No tracked fields for schema: UNKNOWN"
        )

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_delete(self.req, self.resp, "UNKNOWN")

    def test_on_delete_returns_404_for_non_existent_field(self):
        """Test DELETE returns 404 when field doesn't exist"""
        self.req.get_param.side_effect = lambda k: (
            "phone" if k == "type" else "Unknown Label" if k == "label" else None
        )
        self.service.delete_tracked_field.side_effect = NotFoundError(
            "Field not found: type=phone, label=Unknown Label"
        )

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_delete(self.req, self.resp, "ESCHEMA123")

    def test_on_delete_handles_service_error(self):
        """Test DELETE handles service errors"""
        self.req.get_param.side_effect = lambda k: (
            "phone" if k == "type" else "Mobile Phone" if k == "label" else None
        )
        self.service.delete_tracked_field.side_effect = Exception("Database error")

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_delete(self.req, self.resp, "ESCHEMA123")
