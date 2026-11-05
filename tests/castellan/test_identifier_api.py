# -*- encoding: utf-8 -*-
from unittest.mock import AsyncMock, Mock, patch

import falcon
import pytest

from castellan.app.api.identifier import (
    IdentifierKelEnd,
    MultisigIdentifierRegistryCollectionEnd,
    MultisigRegsitrySignatureCollectionEnd,
    MultisigIdentifierCredentialCollectionEnd,
    MultisigCredentialSignatureCollectionEnd,
    RotateWitnessInfoEnd,
    RotateWitnessSignEnd,
)
from castellan.core.services.custom.custom_errors import NotFoundError


class TestMultisigIdentifierCredentialCollectionEnd:
    """Test suite for MultisigIdentifierCredentialCollectionEnd (POST /multisig/identifiers/{multisig_id}/credentials)"""

    def setup_method(self):
        self.service = Mock()
        self.end = MultisigIdentifierCredentialCollectionEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        """Set up request with authenticated account"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_creates_credential_successfully(self, mock_siger_cls):
        """Test POST /credentials creates credential with valid JSON body"""
        self._mock_authenticated_request()

        mock_siger = Mock()
        mock_siger_cls.return_value = mock_siger

        mock_multisig = Mock()
        mock_multisig.id = "multisig123"
        mock_multisig.aid = "EMultisigAID"
        mock_multisig.alias = "test-multisig"
        mock_multisig.oobi = ""
        mock_multisig.mailbox = False
        mock_multisig.created_at = None
        mock_multisig.members = []
        mock_multisig.signing_threshold = 2
        mock_multisig.rotation_threshold = 2
        mock_multisig.key_state = {}
        mock_multisig.current_event = {}
        mock_multisig.current_tel_event = {}
        mock_multisig.mbx = {}
        mock_multisig.rgr = {}
        mock_multisig.registry = None
        mock_multisig.credential = {}
        mock_multisig.grant = {}
        mock_multisig.witness_rotate = None
        mock_multisig.witnesses = []
        mock_multisig.current_metadata = {}

        self.service.create_multisig_credential.return_value = mock_multisig

        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"v": "KERI10JSON000000_", "t": "iss", "d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"v": "KERI10JSON000000_", "t": "ixn", "d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"v": "ACDC10JSON000000_", "d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"v": "KERI10JSON000000_", "t": "exn", "d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        await self.end.on_post(self.req, resp, "multisig123")

        assert resp.status == falcon.HTTP_201
        assert resp.content_type == "application/json"
        self.service.create_multisig_credential.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /credentials returns 401 when no account in context"""
        self.req.context = Mock(spec=[])  # No account attribute
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_iss_missing(self):
        """Test POST /credentials returns 400 when iss is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'iss' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_iss_attachment_missing(self):
        """Test POST /credentials returns 400 when iss_attachment is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'iss_attachment' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_missing(self):
        """Test POST /credentials returns 400 when ixn is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_siger_missing(self):
        """Test POST /credentials returns 400 when ixn_siger is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn_siger' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_credential_missing(self):
        """Test POST /credentials returns 400 when credential is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'credential' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_credential_attachment_missing(self):
        """Test POST /credentials returns 400 when credential_attachment is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'credential_attachment' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_grant_missing(self):
        """Test POST /credentials returns 400 when grant is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'grant' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_grant_siger_missing(self):
        """Test POST /credentials returns 400 when grant_siger is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'grant_siger' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_404_when_multisig_not_found(self, mock_siger_cls):
        """Test POST /credentials returns 404 when multisig not found"""
        self._mock_authenticated_request()
        self.service.create_multisig_credential.side_effect = NotFoundError(
            "Multisig identifier not found"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            await self.end.on_post(self.req, resp, "nonexistent")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_401_when_not_authorized(self, mock_siger_cls):
        """Test POST /credentials returns 401 when account not authorized"""
        self._mock_authenticated_request()
        self.service.create_multisig_credential.side_effect = PermissionError(
            "Account not authorized"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_400_for_value_error(self, mock_siger_cls):
        """Test POST /credentials returns 400 for ValueError"""
        self._mock_authenticated_request()
        self.service.create_multisig_credential.side_effect = ValueError(
            "Failed to parse iss event"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_500_for_unexpected_error(self, mock_siger_cls):
        """Test POST /credentials returns 500 for unexpected errors"""
        self._mock_authenticated_request()
        self.service.create_multisig_credential.side_effect = Exception(
            "Unexpected database error"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "iss": {"d": "ESAID1"},
                "iss_attachment": "-AABAAattachment",
                "ixn": {"d": "ESAID2"},
                "ixn_siger": "AABBsig",
                "credential": {"d": "ESAID3"},
                "credential_attachment": "-AABAAcredattach",
                "grant": {"d": "ESAID4"},
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            await self.end.on_post(self.req, resp, "multisig123")


class TestMultisigCredentialSignatureCollectionEnd:
    """Test suite for MultisigCredentialSignatureCollectionEnd (POST /credentials/signatures)"""

    def setup_method(self):
        self.service = Mock()
        self.end = MultisigCredentialSignatureCollectionEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        """Set up request with authenticated account"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_adds_signatures_successfully(self, mock_siger_cls):
        """Test POST /credentials/signatures adds signatures successfully"""
        self._mock_authenticated_request()

        mock_multisig = Mock()
        mock_multisig.id = "multisig123"
        mock_multisig.aid = "EMultisigAID"
        mock_multisig.alias = "test-multisig"
        mock_multisig.oobi = ""
        mock_multisig.mailbox = False
        mock_multisig.created_at = None
        mock_multisig.members = []
        mock_multisig.signing_threshold = 2
        mock_multisig.rotation_threshold = 2
        mock_multisig.key_state = {}
        mock_multisig.current_event = {}
        mock_multisig.current_tel_event = {}
        mock_multisig.mbx = {}
        mock_multisig.rgr = {}
        mock_multisig.registry = None
        mock_multisig.credential = {}
        mock_multisig.grant = {}
        mock_multisig.witness_rotate = None
        mock_multisig.witnesses = []
        mock_multisig.current_metadata = {}

        self.service.add_multisig_credential_signatures.return_value = mock_multisig

        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        await self.end.on_post(self.req, resp, "multisig123")

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json"
        self.service.add_multisig_credential_signatures.assert_called_once()

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /credentials/signatures returns 401 when no account"""
        self.req.context = Mock(spec=[])  # No account attribute
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_said_missing(self):
        """Test POST /credentials/signatures returns 400 when ixn_said missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn_said' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_siger_missing(self):
        """Test POST /credentials/signatures returns 400 when ixn_siger missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn_siger' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_grant_said_missing(self):
        """Test POST /credentials/signatures returns 400 when grant_said missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'grant_said' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_grant_siger_missing(self):
        """Test POST /credentials/signatures returns 400 when grant_siger missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'grant_siger' is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_404_when_multisig_not_found(self, mock_siger_cls):
        """Test POST /credentials/signatures returns 404 when multisig not found"""
        self._mock_authenticated_request()
        self.service.add_multisig_credential_signatures.side_effect = NotFoundError(
            "Multisig identifier not found"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            await self.end.on_post(self.req, resp, "nonexistent")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_401_when_not_authorized(self, mock_siger_cls):
        """Test POST /credentials/signatures returns 401 when not authorized"""
        self._mock_authenticated_request()
        self.service.add_multisig_credential_signatures.side_effect = PermissionError(
            "Account not authorized"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_400_when_said_mismatch(self, mock_siger_cls):
        """Test POST /credentials/signatures returns 400 when SAIDs don't match"""
        self._mock_authenticated_request()
        self.service.add_multisig_credential_signatures.side_effect = ValueError(
            "IXN SAID does not match pending event"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID_WRONG",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    @patch("castellan.app.api.identifier.Siger")
    async def test_on_post_returns_500_for_unexpected_error(self, mock_siger_cls):
        """Test POST /credentials/signatures returns 500 for unexpected errors"""
        self._mock_authenticated_request()
        self.service.add_multisig_credential_signatures.side_effect = Exception(
            "Database error"
        )
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID123",
                "ixn_siger": "AABBixnsig",
                "grant_said": "ESAID456",
                "grant_siger": "AABBgrantsig",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            await self.end.on_post(self.req, resp, "multisig123")


class TestIdentifierKelEnd:
    """Test suite for IdentifierKelEnd (GET /identifiers/{aid}/kel)"""

    def setup_method(self):
        self.service = Mock()
        self.end = IdentifierKelEnd(self.service)
        self.req = Mock()

    @pytest.mark.asyncio
    async def test_on_get_returns_kel_stream(self):
        """Test GET /identifiers/{aid}/kel returns base64 encoded KEL"""
        self.service.get_kel_stream.return_value = b"KERI-encoded-KEL-bytes"
        resp = Mock()

        await self.end.on_get(self.req, resp, "EAID123")

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json"
        # KEL should be base64 encoded
        import base64

        expected_kel = base64.b64encode(b"KERI-encoded-KEL-bytes").decode("ascii")
        assert resp.media == {"kel": expected_kel}

    @pytest.mark.asyncio
    async def test_on_get_returns_empty_kel(self):
        """Test GET /identifiers/{aid}/kel returns empty KEL when not captured"""
        self.service.get_kel_stream.return_value = b""
        resp = Mock()

        await self.end.on_get(self.req, resp, "EAID123")

        assert resp.status == falcon.HTTP_200
        assert resp.media == {"kel": ""}

    @pytest.mark.asyncio
    async def test_on_get_returns_404_when_not_found(self):
        """Test GET /identifiers/{aid}/kel returns 404 when identifier not found"""
        self.service.get_kel_stream.side_effect = NotFoundError("Identifier not found")
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            await self.end.on_get(self.req, resp, "EUNKNOWN")

    @pytest.mark.asyncio
    async def test_on_get_returns_500_for_unexpected_error(self):
        """Test GET /identifiers/{aid}/kel returns 500 for unexpected errors"""
        self.service.get_kel_stream.side_effect = Exception("Database error")
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            await self.end.on_get(self.req, resp, "EAID123")


class TestMultisigIdentifierRegistryCollectionEnd:
    """Test suite for MultisigIdentifierRegistryCollectionEnd"""

    def setup_method(self):
        self.service = Mock()
        self.end = MultisigIdentifierRegistryCollectionEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /registries returns 401 when no account in context"""
        self.req.context = Mock(spec=[])
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_vcp_missing(self):
        """Test POST /registries returns 400 when vcp is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn": {"d": "ESAID"},
                "mailbox": {"d": "ESAID"},
                "registrar": {"d": "ESAID"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'vcp' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_missing(self):
        """Test POST /registries returns 400 when ixn is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "vcp": {"d": "ESAID"},
                "mailbox": {"d": "ESAID"},
                "registrar": {"d": "ESAID"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_mailbox_missing(self):
        """Test POST /registries returns 400 when mailbox is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "vcp": {"d": "ESAID"},
                "ixn": {"d": "ESAID"},
                "registrar": {"d": "ESAID"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'mailbox' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_registrar_missing(self):
        """Test POST /registries returns 400 when registrar is missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "vcp": {"d": "ESAID"},
                "ixn": {"d": "ESAID"},
                "mailbox": {"d": "ESAID"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'registrar' part is required" in str(exc_info.value.description)


class TestMultisigRegsitrySignatureCollectionEnd:
    """Test suite for MultisigRegsitrySignatureCollectionEnd"""

    def setup_method(self):
        self.service = Mock()
        self.end = MultisigRegsitrySignatureCollectionEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /registries/signatures returns 401 when no account"""
        self.req.context = Mock(spec=[])
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_ixn_said_missing(self):
        """Test POST /registries/signatures returns 400 when ixn_said missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "mailbox_said": "ESAID",
                "registrar_said": "ESAID",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'ixn' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_mailbox_said_missing(self):
        """Test POST /registries/signatures returns 400 when mailbox_said missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID",
                "registrar_said": "ESAID",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'mailbox' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_registrar_said_missing(self):
        """Test POST /registries/signatures returns 400 when registrar_said missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "ixn_said": "ESAID",
                "mailbox_said": "ESAID",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'registrar' part is required" in str(exc_info.value.description)


class TestRotateWitnessInfoEnd:
    """Test suite for RotateWitnessInfoEnd"""

    def setup_method(self):
        self.service = Mock()
        self.end = RotateWitnessInfoEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /witnesses returns 401 when no account"""
        self.req.context = Mock(spec=[])
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_public_key_missing(self):
        """Test POST /witnesses returns 400 when public_key missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "next_key_hash": "hash123",
                "adds": [],
                "cuts": [],
                "witness_threshold": 1,
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "public_key and next_key_hash are required" in str(
            exc_info.value.description
        )

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_adds_not_list(self):
        """Test POST /witnesses returns 400 when adds is not a list"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "public_key": "key123",
                "next_key_hash": "hash123",
                "adds": "not-a-list",
                "cuts": [],
                "witness_threshold": 1,
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'adds' is required and must be a list" in str(
            exc_info.value.description
        )

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_cuts_not_list(self):
        """Test POST /witnesses returns 400 when cuts is not a list"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "public_key": "key123",
                "next_key_hash": "hash123",
                "adds": [],
                "cuts": "not-a-list",
                "witness_threshold": 1,
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'cuts' is required and must be a list" in str(
            exc_info.value.description
        )

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_threshold_not_int(self):
        """Test POST /witnesses returns 400 when witness_threshold is not int"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "public_key": "key123",
                "next_key_hash": "hash123",
                "adds": [],
                "cuts": [],
                "witness_threshold": "not-an-int",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'witness_threshold' is required and must be an integer" in str(
            exc_info.value.description
        )

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_threshold_negative(self):
        """Test POST /witnesses returns 400 when witness_threshold is negative"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "public_key": "key123",
                "next_key_hash": "hash123",
                "adds": [],
                "cuts": [],
                "witness_threshold": -1,
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'witness_threshold' must be >= 0" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_put_returns_401_when_not_authenticated(self):
        """Test PUT /witnesses returns 401 when no account"""
        self.req.context = Mock(spec=[])
        self.req.get_media = AsyncMock(return_value={})
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_put(self.req, resp, "multisig123")


class TestRotateWitnessSignEnd:
    """Test suite for RotateWitnessSignEnd"""

    def setup_method(self):
        self.service = Mock()
        self.end = RotateWitnessSignEnd(self.service)
        self.req = Mock()

    def _mock_authenticated_request(self):
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        self.req.context.account = mock_account
        return mock_account

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_rot_missing(self):
        """Test POST /witnesses/rotate returns 400 when rot missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "sig": "signature123",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'rot' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_400_when_sig_missing(self):
        """Test POST /witnesses/rotate returns 400 when sig missing"""
        self._mock_authenticated_request()
        self.req.get_media = AsyncMock(
            return_value={
                "rot": {"d": "ESAID"},
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest) as exc_info:
            await self.end.on_post(self.req, resp, "multisig123")
        assert "'sig' part is required" in str(exc_info.value.description)

    @pytest.mark.asyncio
    async def test_on_post_returns_401_when_not_authenticated(self):
        """Test POST /witnesses/rotate returns 401 when no account"""
        self.req.context = Mock(spec=[])
        self.req.get_media = AsyncMock(
            return_value={
                "rot": {"d": "ESAID"},
                "sig": "signature123",
            }
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPUnauthorized):
            await self.end.on_post(self.req, resp, "multisig123")
