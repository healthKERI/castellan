# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch, MagicMock

import pytest
from bson import ObjectId
from mongoengine.errors import DoesNotExist

from castellan.core.services.identifier_service import (
    IdentifierService,
    UploadedIdentifier,
)
from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError


class TestIdentifierServiceUpload:
    """Test suite for IdentifierService.upload"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_hby = Mock()
        self.mock_kelSvc = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
            hby=self.mock_hby,
        )

    def test_upload_raises_value_error_when_aid_empty(self):
        """Test upload raises ValueError when aid is empty"""
        with pytest.raises(ValueError, match="aid is required"):
            self.service.upload(aid="", alias="test", kel=b"kel")

    def test_upload_raises_value_error_when_alias_empty(self):
        """Test upload raises ValueError when alias is empty"""
        with pytest.raises(ValueError, match="alias is required"):
            self.service.upload(aid="EAID123", alias="", kel=b"kel")

    def test_upload_raises_value_error_when_kel_empty(self):
        """Test upload raises ValueError when kel is empty"""
        with pytest.raises(ValueError, match="kel is required"):
            self.service.upload(aid="EAID123", alias="test", kel=b"")

    def test_upload_raises_runtime_error_when_parser_none(self):
        """Test upload raises RuntimeError when parser is None"""
        service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            parser=None,
            kvy=self.mock_kvy,
        )
        with pytest.raises(
            RuntimeError, match="requires parser and kvy to process KEL"
        ):
            service.upload(aid="EAID123", alias="test", kel=b"kel")

    def test_upload_raises_runtime_error_when_kvy_none(self):
        """Test upload raises RuntimeError when kvy is None"""
        service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            parser=self.mock_parser,
            kvy=None,
        )
        with pytest.raises(
            RuntimeError, match="requires parser and kvy to process KEL"
        ):
            service.upload(aid="EAID123", alias="test", kel=b"kel")


class TestIdentifierServiceGet:
    """Test suite for IdentifierService.get"""

    def setup_method(self):
        self.service = IdentifierService(
            account_service=Mock(),
            issued_svc=Mock(),
            grant_svc=Mock(),
        )

    @patch("castellan.core.services.identifier_service.UploadedIdentifier.objects")
    def test_get_returns_identifier(self, mock_objects):
        """Test get returns identifier when found"""
        mock_identifier = Mock()
        mock_objects.get.return_value = mock_identifier

        result = self.service.get("EAID123")

        assert result == mock_identifier
        mock_objects.get.assert_called_once_with(aid="EAID123")

    @patch("castellan.core.services.identifier_service.UploadedIdentifier.objects")
    def test_get_raises_not_found_error(self, mock_objects):
        """Test get raises NotFoundError when identifier not found"""
        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Identifier not found"):
            self.service.get("EUNKNOWN")


class TestIdentifierServiceDelete:
    """Test suite for IdentifierService.delete"""

    def setup_method(self):
        self.service = IdentifierService(
            account_service=Mock(),
            issued_svc=Mock(),
            grant_svc=Mock(),
        )

    @patch.object(IdentifierService, "get")
    def test_delete_deletes_identifier(self, mock_get):
        """Test delete removes identifier"""
        mock_identifier = Mock()
        mock_get.return_value = mock_identifier

        self.service.delete("EAID123")

        mock_identifier.delete.assert_called_once()

    @patch.object(IdentifierService, "get")
    def test_delete_raises_not_found_when_not_exists(self, mock_get):
        """Test delete raises NotFoundError when identifier not found"""
        mock_get.side_effect = NotFoundError("Identifier not found: EUNKNOWN")

        with pytest.raises(NotFoundError):
            self.service.delete("EUNKNOWN")


class TestCreateMultisigCredentialValidation:
    """Test suite for IdentifierService.create_multisig_credential input validation"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_hby = Mock()
        self.mock_kelSvc = Mock()
        self.mock_tvy = Mock()
        self.mock_verifier = Mock()
        self.mock_rgy = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
            hby=self.mock_hby,
            tvy=self.mock_tvy,
            verifier=self.mock_verifier,
            rgy=self.mock_rgy,
        )

    def test_raises_value_error_when_multisig_id_empty(self):
        """Test create_multisig_credential raises ValueError when multisig_id empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="multisig_id is required"):
            self.service.create_multisig_credential(
                multisig_id="",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_account_aid_empty(self):
        """Test create_multisig_credential raises ValueError when account_aid empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="account_aid is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_iss_empty(self):
        """Test create_multisig_credential raises ValueError when iss empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="iss is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_iss_attachment_empty(self):
        """Test create_multisig_credential raises ValueError when iss_attachment empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="iss_attachment is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_ixn_empty(self):
        """Test create_multisig_credential raises ValueError when ixn empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="ixn is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_credential_empty(self):
        """Test create_multisig_credential raises ValueError when credential empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="credential is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={},
                credential_attachment="-AAB",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_credential_attachment_empty(self):
        """Test create_multisig_credential raises ValueError when credential_attachment empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="credential_attachment is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="",
                grant={"d": "ESAID"},
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_grant_empty(self):
        """Test create_multisig_credential raises ValueError when grant empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="grant is required"):
            self.service.create_multisig_credential(
                multisig_id="multisig123",
                account_aid="EAccount",
                iss={"d": "ESAID"},
                iss_attachment="-AAB",
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                credential={"d": "ESAID"},
                credential_attachment="-AAB",
                grant={},
                grant_siger=mock_siger,
            )


class TestAddMultisigCredentialSignaturesValidation:
    """Test suite for IdentifierService.add_multisig_credential_signatures input validation"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_hby = Mock()
        self.mock_kelSvc = Mock()
        self.mock_tvy = Mock()
        self.mock_verifier = Mock()
        self.mock_rgy = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
            hby=self.mock_hby,
            tvy=self.mock_tvy,
            verifier=self.mock_verifier,
            rgy=self.mock_rgy,
        )

    def test_raises_value_error_when_multisig_id_empty(self):
        """Test add_multisig_credential_signatures raises ValueError when multisig_id empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="multisig_id is required"):
            self.service.add_multisig_credential_signatures(
                multisig_id="",
                account_aid="EAccount",
                ixn_said="ESAID1",
                ixn_siger=mock_siger,
                grant_said="ESAID2",
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_account_aid_empty(self):
        """Test add_multisig_credential_signatures raises ValueError when account_aid empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="account_aid is required"):
            self.service.add_multisig_credential_signatures(
                multisig_id="multisig123",
                account_aid="",
                ixn_said="ESAID1",
                ixn_siger=mock_siger,
                grant_said="ESAID2",
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_ixn_said_empty(self):
        """Test add_multisig_credential_signatures raises ValueError when ixn_said empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="ixn_said is required"):
            self.service.add_multisig_credential_signatures(
                multisig_id="multisig123",
                account_aid="EAccount",
                ixn_said="",
                ixn_siger=mock_siger,
                grant_said="ESAID2",
                grant_siger=mock_siger,
            )

    def test_raises_value_error_when_grant_said_empty(self):
        """Test add_multisig_credential_signatures raises ValueError when grant_said empty"""
        mock_siger = Mock()
        mock_siger.qb64 = "AABBsig"

        with pytest.raises(ValueError, match="grant_said is required"):
            self.service.add_multisig_credential_signatures(
                multisig_id="multisig123",
                account_aid="EAccount",
                ixn_said="ESAID1",
                ixn_siger=mock_siger,
                grant_said="",
                grant_siger=mock_siger,
            )


class TestCommitMultisigCredential:
    """Test suite for IdentifierService.commit_multisig_credential"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_hby = Mock()
        self.mock_kelSvc = Mock()
        self.mock_tvy = Mock()
        self.mock_verifier = Mock()
        self.mock_rgy = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
            hby=self.mock_hby,
            tvy=self.mock_tvy,
            verifier=self.mock_verifier,
            rgy=self.mock_rgy,
        )

    def test_raises_runtime_error_when_parser_none(self):
        """Test commit_multisig_credential raises RuntimeError when parser is None"""
        service = IdentifierService(
            account_service=Mock(),
            issued_svc=Mock(),
            grant_svc=Mock(),
            parser=None,
            kvy=Mock(),
        )
        mock_multisig = Mock()

        with pytest.raises(
            RuntimeError, match="requires parser and kvy to process KEL"
        ):
            service.commit_multisig_credential(mock_multisig)

    def test_raises_runtime_error_when_kvy_none(self):
        """Test commit_multisig_credential raises RuntimeError when kvy is None"""
        service = IdentifierService(
            account_service=Mock(),
            issued_svc=Mock(),
            grant_svc=Mock(),
            parser=Mock(),
            kvy=None,
        )
        mock_multisig = Mock()

        with pytest.raises(
            RuntimeError, match="requires parser and kvy to process KEL"
        ):
            service.commit_multisig_credential(mock_multisig)


class TestJoinMultisig:
    """Test suite for IdentifierService.join_multisig"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_kelSvc = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
        )

    def test_raises_value_error_when_multisig_id_empty(self):
        """Test join_multisig raises ValueError when multisig_id empty"""
        with pytest.raises(ValueError, match="multisig_id is required"):
            self.service.join_multisig(
                multisig_id="",
                account_aid="EAccount",
                member_aid="EMember",
                kel=b"kel",
            )

    def test_raises_value_error_when_account_aid_empty(self):
        """Test join_multisig raises ValueError when account_aid empty"""
        with pytest.raises(ValueError, match="account_aid is required"):
            self.service.join_multisig(
                multisig_id="multisig123",
                account_aid="",
                member_aid="EMember",
                kel=b"kel",
            )

    def test_raises_value_error_when_member_aid_empty(self):
        """Test join_multisig raises ValueError when member_aid empty"""
        with pytest.raises(ValueError, match="member_aid is required"):
            self.service.join_multisig(
                multisig_id="multisig123",
                account_aid="EAccount",
                member_aid="",
                kel=b"kel",
            )

    def test_raises_value_error_when_kel_empty(self):
        """Test join_multisig raises ValueError when kel empty"""
        with pytest.raises(ValueError, match="kel is required"):
            self.service.join_multisig(
                multisig_id="multisig123",
                account_aid="EAccount",
                member_aid="EMember",
                kel=b"",
            )


class TestSubmitMultisigInception:
    """Test suite for IdentifierService.submit_multisig_inception"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_kelSvc = Mock()
        self.mock_hby = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
            hby=self.mock_hby,
        )

    def test_raises_value_error_when_multisig_id_empty(self):
        """Test submit_multisig_inception raises ValueError when multisig_id empty"""
        with pytest.raises(ValueError, match="multisig_id is required"):
            self.service.submit_multisig_inception(
                multisig_id="",
                account_aid="EAccount",
                data={"aid": "EAID"},
                icp=b"icp",
            )

    def test_raises_value_error_when_account_aid_empty(self):
        """Test submit_multisig_inception raises ValueError when account_aid empty"""
        with pytest.raises(ValueError, match="account_aid is required"):
            self.service.submit_multisig_inception(
                multisig_id="multisig123",
                account_aid="",
                data={"aid": "EAID"},
                icp=b"icp",
            )

    def test_raises_value_error_when_icp_empty(self):
        """Test submit_multisig_inception raises ValueError when icp empty"""
        with pytest.raises(ValueError, match="icp is required"):
            self.service.submit_multisig_inception(
                multisig_id="multisig123",
                account_aid="EAccount",
                data={"aid": "EAID"},
                icp=b"",
            )

    def test_raises_value_error_when_aid_not_in_data(self):
        """Test submit_multisig_inception raises ValueError when aid not in data"""
        with pytest.raises(ValueError, match="data must contain 'aid' key"):
            self.service.submit_multisig_inception(
                multisig_id="multisig123",
                account_aid="EAccount",
                data={},
                icp=b"icp",
            )


class TestCreateMultisigRegistry:
    """Test suite for IdentifierService.create_multisig_registry"""

    def setup_method(self):
        self.mock_account_service = Mock()
        self.mock_issued_svc = Mock()
        self.mock_grant_svc = Mock()
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_kelSvc = Mock()

        self.service = IdentifierService(
            account_service=self.mock_account_service,
            issued_svc=self.mock_issued_svc,
            grant_svc=self.mock_grant_svc,
            kelSvc=self.mock_kelSvc,
            parser=self.mock_parser,
            kvy=self.mock_kvy,
        )

    def test_raises_value_error_when_multisig_id_empty(self):
        """Test create_multisig_registry raises ValueError when multisig_id empty"""
        mock_siger = Mock()

        with pytest.raises(ValueError, match="multisig_id is required"):
            self.service.create_multisig_registry(
                multisig_id="",
                account_aid="EAccount",
                vcp={"d": "ESAID"},
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                mailbox={"d": "ESAID"},
                mailbox_siger=mock_siger,
                registrar={"d": "ESAID"},
                registrar_siger=mock_siger,
                body={"name": "registry"},
            )

    def test_raises_value_error_when_account_aid_empty(self):
        """Test create_multisig_registry raises ValueError when account_aid empty"""
        mock_siger = Mock()

        with pytest.raises(ValueError, match="account_aid is required"):
            self.service.create_multisig_registry(
                multisig_id="multisig123",
                account_aid="",
                vcp={"d": "ESAID"},
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                mailbox={"d": "ESAID"},
                mailbox_siger=mock_siger,
                registrar={"d": "ESAID"},
                registrar_siger=mock_siger,
                body={"name": "registry"},
            )

    def test_raises_value_error_when_vcp_empty(self):
        """Test create_multisig_registry raises ValueError when vcp empty"""
        mock_siger = Mock()

        with pytest.raises(ValueError, match="vcp is required"):
            self.service.create_multisig_registry(
                multisig_id="multisig123",
                account_aid="EAccount",
                vcp={},
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                mailbox={"d": "ESAID"},
                mailbox_siger=mock_siger,
                registrar={"d": "ESAID"},
                registrar_siger=mock_siger,
                body={"name": "registry"},
            )

    def test_raises_value_error_when_name_missing(self):
        """Test create_multisig_registry raises ValueError when name missing"""
        mock_siger = Mock()

        with pytest.raises(ValueError, match="registry name is require"):
            self.service.create_multisig_registry(
                multisig_id="multisig123",
                account_aid="EAccount",
                vcp={"d": "ESAID"},
                ixn={"d": "ESAID"},
                ixn_siger=mock_siger,
                mailbox={"d": "ESAID"},
                mailbox_siger=mock_siger,
                registrar={"d": "ESAID"},
                registrar_siger=mock_siger,
                body={},
            )
