# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from castellan.core.services.custom.custom_errors import NotFoundError, ValidationError
from castellan.core.services.received_credential_service import (
    ReceivedCredentialService,
)
from castellan.core.services.issued_credential_service import flatten_dynamic_fields
from castellan.core.services.dynamic_fields import PhoneField, EmailFieldValue


class TestGetCredentialStream:
    """Test suite for ReceivedCredentialService.get_credential_stream"""

    @patch("castellan.core.services.received_credential_service.serdering.SerderACDC")
    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_does_not_raise_when_tvy_is_none(self, mock_cred_cls, mock_serder_cls):
        """When constructed without a live Tevery (the OOBI-serving case), a
        missing tvy must not block resolving an already-stored credential."""
        service = ReceivedCredentialService(tvy=None)

        mock_cred = Mock()
        mock_cred.sad = {"d": "said123", "v": "ACDC10JSON000000_"}
        mock_cred_cls.objects.get.return_value = mock_cred

        mock_serder = Mock()
        mock_serder.raw = b"acdc-bytes"
        mock_serder_cls.return_value = mock_serder

        result = service.get_credential_stream("said123")

        assert bytes(result) == b"acdc-bytes"

    def test_raises_not_found_when_tvy_set_and_said_missing(self):
        mock_tvy = Mock()
        mock_tvy.tevers = {}
        service = ReceivedCredentialService(tvy=mock_tvy)

        with pytest.raises(NotFoundError, match="Credential not in tevers"):
            service.get_credential_stream("said123")


class TestCaptureSchemaCapture:
    """Test suite for ReceivedCredentialService._capture's optional schema capture"""

    def _make_creder(self):
        creder = Mock()
        creder.regi = "regk123"
        creder.said = "said123"
        creder.sad = {"field": "value"}
        creder.issuer = "issuer_aid"
        creder.issuee = "holder_aid"
        return creder

    def _make_rgy_mock(self):
        mock_rgy = Mock()
        mock_tever = Mock()
        mock_vc_state = Mock()
        mock_vc_state.et = "iss"  # not revoked
        mock_tever.vcState.return_value = mock_vc_state
        mock_rgy.tevers = {"regk123": mock_tever}
        return mock_rgy

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_saves_schema_when_schema_svc_provided(self, mock_cred_cls):
        mock_schema_svc = Mock()
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(
            rgy=mock_rgy, tvy=Mock(), schema_svc=mock_schema_svc
        )

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}, "holder": "holder_aid"}

        result = service._capture(creder, doc)

        mock_schema_svc.save_schema.assert_called_once_with({"$id": "ESAID123"})
        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_skips_schema_save_when_no_schema_svc(self, mock_cred_cls):
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(rgy=mock_rgy, tvy=Mock(), schema_svc=None)

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}, "holder": "holder_aid"}

        result = service._capture(creder, doc)

        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_swallows_schema_svc_exceptions(self, mock_cred_cls):
        """Schema capture is supplementary and must never fail a credential save."""
        mock_schema_svc = Mock()
        mock_schema_svc.save_schema.side_effect = Exception("boom")
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(
            rgy=mock_rgy, tvy=Mock(), schema_svc=mock_schema_svc
        )

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}, "holder": "holder_aid"}

        result = service._capture(creder, doc)

        assert result == mock_cred
        mock_cred.save.assert_called_once()


class TestDynamicFieldsIntegration:
    """Test dynamic fields integration with ReceivedCredential service."""

    def _make_creder(self):
        creder = Mock()
        creder.regi = "regk123"
        creder.said = "said123"
        creder.sad = {"name": "Test Credential", "field": "value"}
        creder.issuer = "issuer_aid"
        creder.issuee = "holder_aid"
        return creder

    def _make_rgy_mock(self):
        mock_rgy = Mock()
        mock_tever = Mock()
        mock_vc_state = Mock()
        mock_vc_state.et = "iss"  # not revoked
        mock_tever.vcState.return_value = mock_vc_state
        mock_rgy.tevers = {"regk123": mock_tever}
        return mock_rgy

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_with_dynamic_fields_in_search_text(self, mock_cred_cls):
        """Test that dynamic field values appear in search_text."""
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(rgy=mock_rgy, tvy=Mock())

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {
            "schema": {},
            "holder": "holder_aid",
            "dynamic_fields": [
                {"type": "email", "label": "Work Email", "value": "test@example.com"},
                {"type": "phone", "label": "Mobile", "value": "+1-555-0123"},
            ],
        }

        result = service._capture(creder, doc)

        # Verify that the credential was created with dynamic_fields
        call_kwargs = mock_cred_cls.call_args[1]
        assert "dynamic_fields" in call_kwargs
        assert len(call_kwargs["dynamic_fields"]) == 2

        # Verify search_text includes dynamic field values
        assert "search_text" in call_kwargs
        search_text = call_kwargs["search_text"]
        assert "test@example.com" in search_text
        assert "+1-555-0123" in search_text
        assert "Work Email" in search_text
        assert "Mobile" in search_text

        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_with_notes_field(self, mock_cred_cls):
        """Test that notes field is captured."""
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(rgy=mock_rgy, tvy=Mock())

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {
            "schema": {},
            "holder": "holder_aid",
            "notes": "This is a test note",
        }

        result = service._capture(creder, doc)

        # Verify notes field was captured
        call_kwargs = mock_cred_cls.call_args[1]
        assert "notes" in call_kwargs
        assert call_kwargs["notes"] == "This is a test note"

        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_capture_handles_invalid_dynamic_field_gracefully(self, mock_cred_cls):
        """Test that invalid field types are logged but don't crash save."""
        mock_rgy = self._make_rgy_mock()
        service = ReceivedCredentialService(rgy=mock_rgy, tvy=Mock())

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {
            "schema": {},
            "holder": "holder_aid",
            "dynamic_fields": [
                {"type": "invalid_type", "label": "Test", "value": "value"}
            ],
        }

        # Should not raise, just log warning
        result = service._capture(creder, doc)

        # Credential should still be saved with empty dynamic_fields
        call_kwargs = mock_cred_cls.call_args[1]
        assert call_kwargs["dynamic_fields"] == []
        assert result == mock_cred

    def test_flatten_dynamic_fields_function(self):
        """Test flatten_dynamic_fields helper function."""
        fields = [
            PhoneField(label="Mobile", value="+1-555-0123"),
            EmailFieldValue(label="Email", value="test@example.com"),
        ]

        result = flatten_dynamic_fields(fields)

        assert "Mobile" in result
        assert "+1-555-0123" in result
        assert "Email" in result
        assert "test@example.com" in result

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_update_credential_with_notes(self, mock_cred_cls):
        """Test updating credential notes field."""
        service = ReceivedCredentialService()

        # Mock existing credential
        mock_cred = Mock()
        mock_cred.sad = {"name": "Test"}
        mock_cred_cls.objects.get.return_value = mock_cred

        update_data = {"notes": "Updated note content"}

        result = service.update_credential("said123", update_data)

        # Verify notes was updated
        assert mock_cred.notes == "Updated note content"

        mock_cred.save.assert_called_once()
        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_update_credential_with_dynamic_fields(self, mock_cred_cls):
        """Test updating credential dynamic fields rebuilds search_text."""
        service = ReceivedCredentialService()

        # Mock existing credential
        mock_cred = Mock()
        mock_cred.sad = {"name": "Test"}
        mock_cred_cls.objects.get.return_value = mock_cred

        update_data = {
            "dynamic_fields": [
                {"type": "text", "label": "Note", "value": "Updated note"}
            ]
        }

        result = service.update_credential("said123", update_data)

        # Verify dynamic_fields was updated
        assert len(mock_cred.dynamic_fields) == 1
        assert mock_cred.dynamic_fields[0].label == "Note"

        # Verify search_text was rebuilt
        assert "Updated note" in mock_cred.search_text
        assert "Note" in mock_cred.search_text

        mock_cred.save.assert_called_once()
        assert result == mock_cred

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_update_credential_validates_dynamic_fields_is_list(self, mock_cred_cls):
        """Test that update_credential validates dynamic_fields is a list."""
        service = ReceivedCredentialService()

        mock_cred = Mock()
        mock_cred_cls.objects.get.return_value = mock_cred

        update_data = {"dynamic_fields": "not a list"}

        with pytest.raises(ValidationError, match="dynamic_fields must be a list"):
            service.update_credential("said123", update_data)

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_update_credential_raises_on_invalid_field_type(self, mock_cred_cls):
        """Test that invalid field types raise ValidationError."""
        service = ReceivedCredentialService()

        mock_cred = Mock()
        mock_cred_cls.objects.get.return_value = mock_cred

        update_data = {
            "dynamic_fields": [{"type": "invalid", "label": "Test", "value": "value"}]
        }

        with pytest.raises(ValidationError, match="Invalid dynamic field data"):
            service.update_credential("said123", update_data)

    @patch("castellan.core.services.received_credential_service.ReceivedCredential")
    def test_update_credential_with_multiple_fields(self, mock_cred_cls):
        """Test updating multiple fields at once (notes, dynamic_fields, status)."""
        service = ReceivedCredentialService()

        # Mock existing credential
        mock_cred = Mock()
        mock_cred.sad = {"name": "Test"}
        mock_cred_cls.objects.get.return_value = mock_cred

        update_data = {
            "status": "revoked",
            "notes": "Credential revoked by issuer",
            "dynamic_fields": [
                {"type": "date", "label": "Revoked Date", "value": "2025-01-15"}
            ],
        }

        result = service.update_credential("said123", update_data)

        # Verify all fields were updated
        assert mock_cred.status == "revoked"
        assert mock_cred.notes == "Credential revoked by issuer"
        assert len(mock_cred.dynamic_fields) == 1

        # Verify search_text was rebuilt
        assert "Revoked Date" in mock_cred.search_text

        mock_cred.save.assert_called_once()
        assert result == mock_cred
