# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch

import falcon
import pytest

from castellan.app.api.oobi import (
    OOBI_AID_HEADER,
    CredentialOobiEnd,
    OobiDispatchEnd,
    ServerOobiEnd,
)
from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.key_event_log_service import Aid


class TestOobiDispatchEnd:
    """Test suite for OobiDispatchEnd (GET /oobi/{id})"""

    def setup_method(self):
        self.kel_svc = Mock()
        self.schema_svc = Mock()
        self.end = OobiDispatchEnd(self.kel_svc, self.schema_svc)
        self.req = Mock()

    @patch("castellan.app.api.oobi.KeyEventLogService.get_aid")
    def test_on_get_resolves_known_aid_as_keystate(self, mock_get_aid):
        mock_get_aid.return_value = Mock()
        self.kel_svc.get_full_stream.return_value = bytearray(b"kel-bytes")
        resp = Mock()

        self.end.on_get(self.req, resp, "test_aid")

        mock_get_aid.assert_called_once_with("test_aid")
        self.kel_svc.get_full_stream.assert_called_once_with("test_aid")
        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json+cesr"
        resp.set_header.assert_called_once_with(OOBI_AID_HEADER, "test_aid")
        assert resp.data == bytes(b"kel-bytes")
        self.schema_svc.get_schema.assert_not_called()

    @patch("castellan.app.api.oobi.KeyEventLogService.get_aid")
    def test_on_get_resolves_known_schema(self, mock_get_aid):
        mock_get_aid.side_effect = Aid.DoesNotExist()
        mock_schema = Mock()
        mock_schema.raw = b"schema-bytes"
        self.schema_svc.get_schema.return_value = mock_schema
        resp = Mock()

        self.end.on_get(self.req, resp, "ESAID123")

        self.schema_svc.get_schema.assert_called_once_with("ESAID123")
        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/schema+json"
        assert resp.data == b"schema-bytes"

    @patch("castellan.app.api.oobi.KeyEventLogService.get_aid")
    def test_on_get_raises_404_when_neither_aid_nor_schema_found(self, mock_get_aid):
        mock_get_aid.side_effect = Aid.DoesNotExist()
        self.schema_svc.get_schema.side_effect = NotFoundError("Schema not found")
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_get(self.req, resp, "unknown-id")


class TestCredentialOobiEnd:
    """Test suite for CredentialOobiEnd (GET /oobi/{said}/credential)"""

    def setup_method(self):
        self.issued_svc = Mock()
        self.received_svc = Mock()
        self.end = CredentialOobiEnd(self.issued_svc, self.received_svc)
        self.req = Mock()

    def test_on_get_resolves_issued_credential(self):
        self.issued_svc.get_credential_stream.return_value = bytearray(b"issued-bytes")
        resp = Mock()

        self.end.on_get(self.req, resp, "said123")

        self.issued_svc.get_credential_stream.assert_called_once_with("said123")
        self.received_svc.get_credential_stream.assert_not_called()
        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json+cesr"
        assert resp.data == bytes(b"issued-bytes")

    def test_on_get_falls_back_to_received_credential(self):
        self.issued_svc.get_credential_stream.side_effect = NotFoundError("not issued")
        self.received_svc.get_credential_stream.return_value = bytearray(
            b"received-bytes"
        )
        resp = Mock()

        self.end.on_get(self.req, resp, "said123")

        self.received_svc.get_credential_stream.assert_called_once_with("said123")
        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json+cesr"
        assert resp.data == bytes(b"received-bytes")

    def test_on_get_raises_404_when_neither_found(self):
        self.issued_svc.get_credential_stream.side_effect = NotFoundError("not issued")
        self.received_svc.get_credential_stream.side_effect = NotFoundError(
            "not received"
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_get(self.req, resp, "said123")


class TestServerOobiEnd:
    """Test suite for ServerOobiEnd (GET /oobi/server)"""

    def setup_method(self):
        self.server_svc = Mock()
        self.kel_svc = Mock()
        self.end = ServerOobiEnd(self.server_svc, self.kel_svc)
        self.req = Mock()

    def test_on_get_resolves_active_server(self):
        mock_server = Mock()
        mock_server.aid = "server_aid_123"
        self.server_svc.get_active_server.return_value = mock_server
        self.kel_svc.get_full_stream.return_value = bytearray(b"server-kel-bytes")
        resp = Mock()

        self.end.on_get(self.req, resp)

        self.kel_svc.get_full_stream.assert_called_once_with("server_aid_123")
        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json+cesr"
        resp.set_header.assert_called_once_with(OOBI_AID_HEADER, "server_aid_123")
        assert resp.data == bytes(b"server-kel-bytes")

    def test_on_get_raises_404_when_no_active_server(self):
        self.server_svc.get_active_server.return_value = None
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_get(self.req, resp)

        self.kel_svc.get_full_stream.assert_not_called()

    def test_on_get_raises_404_when_kel_stream_empty(self):
        mock_server = Mock()
        mock_server.aid = "server_aid_123"
        self.server_svc.get_active_server.return_value = mock_server
        self.kel_svc.get_full_stream.return_value = bytearray()
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_get(self.req, resp)
