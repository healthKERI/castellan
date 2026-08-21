# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.schema_service import Schema, SchemaService


class TestSchemaService:
    """Test suite for SchemaService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.service = SchemaService()

    @patch("castellan.core.services.schema_service.Schema")
    @patch("castellan.core.services.schema_service.Schemer")
    def test_save_schema_creates_new_schema(self, mock_schemer_cls, mock_schema_cls):
        """Test that save_schema derives the SAID and persists a new Schema doc"""
        mock_schemer = Mock()
        mock_schemer.said = "ESAID123"
        mock_schemer.sed = {"$id": "ESAID123"}
        mock_schemer.raw = b"raw-bytes"
        mock_schemer_cls.return_value = mock_schemer

        mock_schema_cls.objects.return_value.first.return_value = None
        mock_schema = Mock()
        mock_schema_cls.return_value = mock_schema

        result = self.service.save_schema({"$id": "ESAID123"})

        mock_schemer_cls.assert_called_once_with(sed={"$id": "ESAID123"})
        mock_schema_cls.objects.assert_called_once_with(said="ESAID123")
        mock_schema_cls.assert_called_once_with(
            said="ESAID123", sed={"$id": "ESAID123"}, raw=b"raw-bytes"
        )
        mock_schema.save.assert_called_once()
        assert result == mock_schema

    @patch("castellan.core.services.schema_service.Schema")
    @patch("castellan.core.services.schema_service.Schemer")
    def test_save_schema_is_idempotent(self, mock_schemer_cls, mock_schema_cls):
        """Test that a second save_schema call with the same sed returns the
        existing document without re-saving"""
        mock_schemer = Mock()
        mock_schemer.said = "ESAID123"
        mock_schemer_cls.return_value = mock_schemer

        existing_schema = Mock()
        mock_schema_cls.objects.return_value.first.return_value = existing_schema

        result = self.service.save_schema({"$id": "ESAID123"})

        assert result == existing_schema
        mock_schema_cls.assert_not_called()

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_get_schema_returns_schema_when_found(self, mock_objects):
        """Test that get_schema returns the Schema document when found"""
        mock_schema = Mock()
        mock_objects.get.return_value = mock_schema

        result = self.service.get_schema("ESAID123")

        assert result == mock_schema
        mock_objects.get.assert_called_once_with(said="ESAID123")

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_get_schema_raises_not_found_error(self, mock_objects):
        """Test that get_schema raises NotFoundError when the schema is missing"""
        mock_objects.get.side_effect = Schema.DoesNotExist()

        with pytest.raises(NotFoundError, match="Schema not found"):
            self.service.get_schema("unknown")

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_list_schemas_with_defaults(self, mock_objects):
        """Test that list_schemas returns paginated results with default params"""
        mock_schema1 = Mock()
        mock_schema2 = Mock()
        mock_qs = Mock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 2
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = [mock_schema1, mock_schema2]
        mock_objects.return_value = mock_qs

        schemas, total, num_pages = self.service.list_schemas()

        assert schemas == [mock_schema1, mock_schema2]
        assert total == 2
        assert num_pages == 1
        mock_qs.order_by.assert_called_once_with("-created_at")
        mock_qs.skip.assert_called_once_with(0)
        mock_qs.limit.assert_called_once_with(20)

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_list_schemas_with_pagination(self, mock_objects):
        """Test that list_schemas handles pagination correctly"""
        mock_qs = Mock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 42
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        schemas, total, num_pages = self.service.list_schemas(page=1, page_size=10)

        assert total == 42
        assert num_pages == 5
        mock_qs.skip.assert_called_once_with(10)
        mock_qs.limit.assert_called_once_with(10)

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_list_schemas_with_custom_order(self, mock_objects):
        """Test that list_schemas respects custom ordering"""
        mock_qs = Mock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        schemas, total, num_pages = self.service.list_schemas(
            order=["-created_at", "said"]
        )

        mock_qs.order_by.assert_called_once_with("-created_at", "said")

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_list_schemas_empty_results(self, mock_objects):
        """Test that list_schemas handles empty results correctly"""
        mock_qs = Mock()
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        schemas, total, num_pages = self.service.list_schemas()

        assert schemas == []
        assert total == 0
        assert num_pages == 1

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_delete_schema_success(self, mock_objects):
        """Test that delete_schema successfully deletes a schema"""
        mock_schema = Mock()
        mock_objects.get.return_value = mock_schema

        self.service.delete_schema("ESAID123")

        mock_objects.get.assert_called_once_with(said="ESAID123")
        mock_schema.delete.assert_called_once()

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_delete_schema_not_found(self, mock_objects):
        """Test that delete_schema raises NotFoundError when schema doesn't exist"""
        mock_objects.get.side_effect = Schema.DoesNotExist()

        with pytest.raises(NotFoundError, match="Schema not found"):
            self.service.delete_schema("unknown")

    @patch("castellan.core.services.schema_service.Schema.objects")
    def test_delete_schema_error_handling(self, mock_objects):
        """Test that delete_schema handles deletion errors"""
        mock_schema = Mock()
        mock_schema.delete.side_effect = Exception("Database error")
        mock_objects.get.return_value = mock_schema

        with pytest.raises(RuntimeError, match="Error deleting schema"):
            self.service.delete_schema("ESAID123")
