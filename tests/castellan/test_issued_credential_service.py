# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch

import pytest

from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.issued_credential_service import IssuedCredentialService


class TestGetCredentialStream:
    """Test suite for IssuedCredentialService.get_credential_stream"""

    @patch("castellan.core.services.issued_credential_service.serdering.SerderKERI")
    @patch("castellan.core.services.issued_credential_service.IssuedCredential")
    def test_does_not_raise_when_tvy_is_none(self, mock_cred_cls, mock_serder_cls):
        """When constructed without a live Tevery (the OOBI-serving case), a
        missing tvy must not block resolving an already-stored credential."""
        service = IssuedCredentialService(tvy=None)

        mock_cred = Mock()
        mock_cred.sad = {"d": "said123"}
        mock_cred_cls.objects.get.return_value = mock_cred

        mock_serder = Mock()
        mock_serder.raw = b"acdc-bytes"
        mock_serder_cls.return_value = mock_serder

        result = service.get_credential_stream("said123")

        assert bytes(result) == b"acdc-bytes"

    def test_raises_not_found_when_tvy_set_and_said_missing(self):
        mock_tvy = Mock()
        mock_tvy.tevers = {}
        service = IssuedCredentialService(tvy=mock_tvy)

        with pytest.raises(NotFoundError, match="Credential not in tevers"):
            service.get_credential_stream("said123")


class TestCaptureSchemaCapture:
    """Test suite for IssuedCredentialService._capture's optional schema capture"""

    def _make_creder(self):
        creder = Mock()
        creder.regi = "regk123"
        creder.said = "said123"
        creder.sad = {"field": "value"}
        creder.issuer = "issuer_aid"
        creder.issuee = "recipient_aid"
        return creder

    @patch("castellan.core.services.issued_credential_service.IssuedCredential")
    def test_capture_saves_schema_when_schema_svc_provided(self, mock_cred_cls):
        mock_schema_svc = Mock()
        service = IssuedCredentialService(
            rgy=Mock(), tvy=Mock(), schema_svc=mock_schema_svc
        )

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}}

        result = service._capture(creder, doc)

        mock_schema_svc.save_schema.assert_called_once_with({"$id": "ESAID123"})
        assert result == mock_cred

    @patch("castellan.core.services.issued_credential_service.IssuedCredential")
    def test_capture_skips_schema_save_when_no_schema_svc(self, mock_cred_cls):
        service = IssuedCredentialService(rgy=Mock(), tvy=Mock(), schema_svc=None)

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}}

        result = service._capture(creder, doc)

        assert result == mock_cred

    @patch("castellan.core.services.issued_credential_service.IssuedCredential")
    def test_capture_swallows_schema_svc_exceptions(self, mock_cred_cls):
        """Schema capture is supplementary and must never fail a credential save."""
        mock_schema_svc = Mock()
        mock_schema_svc.save_schema.side_effect = Exception("boom")
        service = IssuedCredentialService(
            rgy=Mock(), tvy=Mock(), schema_svc=mock_schema_svc
        )

        mock_cred = Mock()
        mock_cred_cls.return_value = mock_cred

        creder = self._make_creder()
        doc = {"schema": {"$id": "ESAID123"}}

        result = service._capture(creder, doc)

        assert result == mock_cred
        mock_cred.save.assert_called_once()
