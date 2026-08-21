# -*- encoding: utf-8 -*-
from datetime import datetime
from unittest.mock import Mock

import falcon
import pytest

from castellan.app.api.json_schema import (
    JsonSchemaCollectionEnd,
    JsonSchemaResourceEnd,
)
from castellan.core.services.custom.custom_errors import NotFoundError


class TestJsonSchemaCollectionEnd:
    """Test suite for JsonSchemaCollectionEnd (GET /schemas and POST /schemas)"""

    def setup_method(self):
        self.service = Mock()
        self.end = JsonSchemaCollectionEnd(self.service)
        self.req = Mock()

    def test_on_get_returns_paginated_schemas(self):
        """Test GET /schemas returns paginated list of schemas"""
        mock_schema1 = Mock()
        mock_schema1.said = "ESAID1"
        mock_schema1.sed = {"$id": "ESAID1", "type": "object"}
        mock_schema1.created_at = datetime(2024, 1, 15, 10, 30, 0)

        mock_schema2 = Mock()
        mock_schema2.said = "ESAID2"
        mock_schema2.sed = {"$id": "ESAID2", "type": "object"}
        mock_schema2.created_at = datetime(2024, 1, 16, 11, 30, 0)

        self.service.list_schemas.return_value = ([mock_schema1, mock_schema2], 2, 1)
        self.req.get_param_as_int.side_effect = lambda k, default: default
        self.req.get_param_as_list.return_value = None
        resp = Mock()

        self.end.on_get(self.req, resp)

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json"
        assert resp.media == {
            "count": 2,
            "page": 0,
            "num_pages": 1,
            "schemas": [
                {
                    "said": "ESAID1",
                    "schema": {"$id": "ESAID1", "type": "object"},
                    "created_at": "2024-01-15T10:30:00",
                },
                {
                    "said": "ESAID2",
                    "schema": {"$id": "ESAID2", "type": "object"},
                    "created_at": "2024-01-16T11:30:00",
                },
            ],
        }

    def test_on_get_with_pagination_params(self):
        """Test GET /schemas respects pagination parameters"""
        self.service.list_schemas.return_value = ([], 42, 5)
        self.req.get_param_as_int.side_effect = lambda k, default: (
            1 if k == "page" else 10 if k == "page_size" else default
        )
        self.req.get_param_as_list.return_value = ["-created_at"]
        resp = Mock()

        self.end.on_get(self.req, resp)

        self.service.list_schemas.assert_called_once_with(
            page=1,
            page_size=10,
            order=["-created_at"],
        )
        assert resp.media["count"] == 42
        assert resp.media["page"] == 1
        assert resp.media["num_pages"] == 5

    def test_on_get_handles_service_error(self):
        """Test GET /schemas handles service errors"""
        self.service.list_schemas.side_effect = Exception("Database error")
        self.req.get_param_as_int.side_effect = lambda k, default: default
        self.req.get_param_as_list.return_value = None
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_get(self.req, resp)

    def test_on_post_uploads_schema_successfully(self):
        """Test POST /schemas successfully uploads a schema"""
        mock_part = Mock()
        mock_part.name = "schema"
        mock_part.content_type = "application/json"
        mock_part.get_media.return_value = {
            "$id": "ESAID123",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
        }

        self.req.get_media.return_value = [mock_part]

        mock_schema = Mock()
        mock_schema.said = "ESAID123"
        mock_schema.sed = {
            "$id": "ESAID123",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
        }
        mock_schema.created_at = datetime(2024, 1, 15, 10, 30, 0)
        self.service.save_schema.return_value = mock_schema

        resp = Mock()

        self.end.on_post(self.req, resp)

        self.service.save_schema.assert_called_once_with(
            {
                "$id": "ESAID123",
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
            }
        )
        assert resp.status == falcon.HTTP_201
        assert resp.media == {
            "said": "ESAID123",
            "schema": {
                "$id": "ESAID123",
                "$schema": "http://json-schema.org/draft-07/schema#",
                "type": "object",
            },
            "created_at": "2024-01-15T10:30:00",
        }

    def test_on_post_rejects_wrong_content_type(self):
        """Test POST /schemas rejects non-JSON content type"""
        mock_part = Mock()
        mock_part.name = "schema"
        mock_part.content_type = "text/plain"

        self.req.get_media.return_value = [mock_part]
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp)

    def test_on_post_rejects_unexpected_form_part(self):
        """Test POST /schemas rejects unexpected form parts"""
        mock_part = Mock()
        mock_part.name = "unexpected"

        self.req.get_media.return_value = [mock_part]
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp)

    def test_on_post_rejects_missing_schema_part(self):
        """Test POST /schemas rejects missing schema part"""
        self.req.get_media.return_value = []
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp)

    def test_on_post_rejects_non_dict_schema(self):
        """Test POST /schemas rejects non-dict schema"""
        mock_part = Mock()
        mock_part.name = "schema"
        mock_part.content_type = "application/json"
        mock_part.get_media.return_value = ["not", "a", "dict"]

        self.req.get_media.return_value = [mock_part]
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp)

    def test_on_post_rejects_schema_without_id_field(self):
        """Test POST /schemas rejects schema without $id field"""
        mock_part = Mock()
        mock_part.name = "schema"
        mock_part.content_type = "application/json"
        mock_part.get_media.return_value = {"type": "object"}

        self.req.get_media.return_value = [mock_part]
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp)

    def test_on_post_handles_service_error(self):
        """Test POST /schemas handles service errors"""
        mock_part = Mock()
        mock_part.name = "schema"
        mock_part.content_type = "application/json"
        mock_part.get_media.return_value = {
            "$id": "ESAID123",
            "type": "object",
        }

        self.req.get_media.return_value = [mock_part]
        self.service.save_schema.side_effect = Exception("Database error")
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_post(self.req, resp)


class TestJsonSchemaResourceEnd:
    """Test suite for JsonSchemaResourceEnd (GET /schemas/{said} and DELETE /schemas/{said})"""

    def setup_method(self):
        self.service = Mock()
        self.end = JsonSchemaResourceEnd(self.service)
        self.req = Mock()

    def test_on_get_returns_schema_as_json(self):
        """Test GET /schemas/{said} returns schema as JSON"""
        mock_schema = Mock()
        mock_schema.said = "ESAID123"
        mock_schema.sed = {"$id": "ESAID123", "type": "object"}
        mock_schema.created_at = datetime(2024, 1, 15, 10, 30, 0)
        mock_schema.raw = b'{"$id":"ESAID123","type":"object"}'

        self.service.get_schema.return_value = mock_schema
        self.req.get_param_as_bool.return_value = False
        resp = Mock()

        self.end.on_get(self.req, resp, "ESAID123")

        self.service.get_schema.assert_called_once_with("ESAID123")
        assert resp.status == falcon.HTTP_200
        assert resp.media == {
            "said": "ESAID123",
            "schema": {"$id": "ESAID123", "type": "object"},
            "created_at": "2024-01-15T10:30:00",
        }

    def test_on_get_returns_schema_as_stream(self):
        """Test GET /schemas/{said}?stream=true returns raw schema bytes"""
        mock_schema = Mock()
        mock_schema.said = "ESAID123"
        mock_schema.raw = b'{"$id":"ESAID123","type":"object"}'

        self.service.get_schema.return_value = mock_schema
        self.req.get_param_as_bool.return_value = True
        resp = Mock()

        self.end.on_get(self.req, resp, "ESAID123")

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/schema+json"
        assert resp.data == b'{"$id":"ESAID123","type":"object"}'

    def test_on_get_raises_404_when_not_found(self):
        """Test GET /schemas/{said} raises 404 when schema not found"""
        self.service.get_schema.side_effect = NotFoundError("Schema not found")
        self.req.get_param_as_bool.return_value = False
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_get(self.req, resp, "unknown")

    def test_on_get_handles_service_error(self):
        """Test GET /schemas/{said} handles service errors"""
        self.service.get_schema.side_effect = Exception("Database error")
        self.req.get_param_as_bool.return_value = False
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_get(self.req, resp, "ESAID123")

    def test_on_delete_removes_schema(self):
        """Test DELETE /schemas/{said} successfully removes a schema"""
        resp = Mock()

        self.end.on_delete(self.req, resp, "ESAID123")

        self.service.delete_schema.assert_called_once_with("ESAID123")
        assert resp.status == falcon.HTTP_204

    def test_on_delete_raises_404_when_not_found(self):
        """Test DELETE /schemas/{said} raises 404 when schema not found"""
        self.service.delete_schema.side_effect = NotFoundError("Schema not found")
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_delete(self.req, resp, "unknown")

    def test_on_delete_handles_service_error(self):
        """Test DELETE /schemas/{said} handles service errors"""
        self.service.delete_schema.side_effect = Exception("Database error")
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_delete(self.req, resp, "ESAID123")
