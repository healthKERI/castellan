# -*- encoding: utf-8 -*-
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from castellan.core.services.custom.custom_errors import NotFoundError
from castellan.core.services.grant_service import GrantService


class TestGrantService:
    """Test suite for GrantService"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_hby = Mock()
        self.service = GrantService(hby=self.mock_hby)

    # ==========================================================================
    # get_grant tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_get_grant_returns_grant_when_found(self, mock_objects):
        """Test that get_grant returns the Grant document when found"""
        mock_grant = Mock()
        mock_objects.get.return_value = mock_grant

        result = GrantService.get_grant("EGrantSAID123")

        assert result == mock_grant
        mock_objects.get.assert_called_once_with(said="EGrantSAID123")

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_get_grant_raises_not_found_error(self, mock_objects):
        """Test that get_grant raises NotFoundError when grant is missing"""
        from mongoengine import DoesNotExist

        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Grant not found: unknown"):
            GrantService.get_grant("unknown")

    # ==========================================================================
    # list_grants tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_list_grants_with_defaults(self, mock_objects):
        """Test that list_grants returns paginated results with default params"""
        mock_grant1 = Mock()
        mock_grant2 = Mock()
        mock_qs = Mock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 2
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = [mock_grant1, mock_grant2]
        mock_objects.return_value = mock_qs

        grants, total, num_pages = GrantService.list_grants()

        assert grants == [mock_grant1, mock_grant2]
        assert total == 2
        assert num_pages == 1
        mock_qs.order_by.assert_called_once_with("-created_at")
        mock_qs.skip.assert_called_once_with(0)
        mock_qs.limit.assert_called_once_with(20)

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_list_grants_with_pagination(self, mock_objects):
        """Test that list_grants handles pagination correctly"""
        mock_qs = Mock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 42
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        grants, total, num_pages = GrantService.list_grants(page=1, page_size=10)

        assert total == 42
        assert num_pages == 5
        mock_qs.skip.assert_called_once_with(10)
        mock_qs.limit.assert_called_once_with(10)

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_list_grants_with_filter_term(self, mock_objects):
        """Test that list_grants filters by search term"""
        mock_qs = Mock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 1
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = [Mock()]
        mock_objects.return_value = mock_qs

        grants, total, num_pages = GrantService.list_grants(filter_term="test")

        assert total == 1
        mock_qs.filter.assert_called_once()

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_list_grants_with_custom_order(self, mock_objects):
        """Test that list_grants respects custom ordering"""
        mock_qs = Mock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        GrantService.list_grants(order=["-created_at", "said"])

        mock_qs.order_by.assert_called_once_with("-created_at", "said")

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_list_grants_empty_results(self, mock_objects):
        """Test that list_grants handles empty results correctly"""
        mock_qs = Mock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.order_by.return_value = mock_qs
        mock_qs.count.return_value = 0
        mock_qs.skip.return_value = mock_qs
        mock_qs.limit.return_value = []
        mock_objects.return_value = mock_qs

        grants, total, num_pages = GrantService.list_grants()

        assert grants == []
        assert total == 0
        assert num_pages == 1

    # ==========================================================================
    # update_grant tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_updates_event(self, mock_objects):
        """Test that update_grant updates the event field"""
        mock_grant = Mock()
        mock_grant.event = {"old": "data"}
        mock_objects.get.return_value = mock_grant

        result = GrantService.update_grant(
            said="EGrantSAID123",
            event={"new": "data"},
        )

        assert mock_grant.event == {"new": "data"}
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_updates_signatures(self, mock_objects):
        """Test that update_grant updates the signatures field"""
        mock_grant = Mock()
        mock_grant.signatures = ["old_sig"]
        mock_objects.get.return_value = mock_grant

        result = GrantService.update_grant(
            said="EGrantSAID123",
            signatures=["new_sig1", "new_sig2"],
        )

        assert mock_grant.signatures == ["new_sig1", "new_sig2"]
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_updates_pathed(self, mock_objects):
        """Test that update_grant updates the pathed field"""
        mock_grant = Mock()
        mock_grant.pathed = "old_pathed"
        mock_objects.get.return_value = mock_grant

        result = GrantService.update_grant(
            said="EGrantSAID123",
            pathed="new_pathed",
        )

        assert mock_grant.pathed == "new_pathed"
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_updates_all_fields(self, mock_objects):
        """Test that update_grant can update all fields at once"""
        mock_grant = Mock()
        mock_objects.get.return_value = mock_grant

        result = GrantService.update_grant(
            said="EGrantSAID123",
            event={"new": "event"},
            signatures=["sig1", "sig2"],
            pathed="new_pathed",
        )

        assert mock_grant.event == {"new": "event"}
        assert mock_grant.signatures == ["sig1", "sig2"]
        assert mock_grant.pathed == "new_pathed"
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_updates_timestamp(self, mock_objects):
        """Test that update_grant updates the updated_at timestamp"""
        mock_grant = Mock()
        old_timestamp = datetime(2024, 1, 1)
        mock_grant.updated_at = old_timestamp
        mock_objects.get.return_value = mock_grant

        GrantService.update_grant(said="EGrantSAID123", event={"new": "data"})

        assert mock_grant.updated_at != old_timestamp

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_update_grant_raises_not_found_error(self, mock_objects):
        """Test that update_grant raises NotFoundError when grant is missing"""
        from mongoengine import DoesNotExist

        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Grant not found: unknown"):
            GrantService.update_grant(said="unknown", event={"new": "data"})

    # ==========================================================================
    # add_signature tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_add_signature_success(self, mock_objects):
        """Test that add_signature appends a signature to the list"""
        mock_grant = Mock()
        mock_grant.signatures = ["existing_sig"]
        mock_objects.get.return_value = mock_grant

        result = GrantService.add_signature(
            said="EGrantSAID123",
            signature="new_sig",
        )

        assert "new_sig" in mock_grant.signatures
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_add_signature_to_empty_list(self, mock_objects):
        """Test that add_signature works with an empty signatures list"""
        mock_grant = Mock()
        mock_grant.signatures = []
        mock_objects.get.return_value = mock_grant

        result = GrantService.add_signature(
            said="EGrantSAID123",
            signature="first_sig",
        )

        assert mock_grant.signatures == ["first_sig"]
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_add_signature_updates_timestamp(self, mock_objects):
        """Test that add_signature updates the updated_at timestamp"""
        mock_grant = Mock()
        mock_grant.signatures = []
        old_timestamp = datetime(2024, 1, 1)
        mock_grant.updated_at = old_timestamp
        mock_objects.get.return_value = mock_grant

        GrantService.add_signature(said="EGrantSAID123", signature="sig")

        assert mock_grant.updated_at != old_timestamp

    def test_add_signature_raises_value_error_when_signature_empty(self):
        """Test that add_signature raises ValueError when signature is empty"""
        with pytest.raises(ValueError, match="signature is required"):
            GrantService.add_signature(said="EGrantSAID123", signature="")

    def test_add_signature_raises_value_error_when_signature_none(self):
        """Test that add_signature raises ValueError when signature is None"""
        with pytest.raises(ValueError, match="signature is required"):
            GrantService.add_signature(said="EGrantSAID123", signature=None)

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_add_signature_raises_not_found_error(self, mock_objects):
        """Test that add_signature raises NotFoundError when grant is missing"""
        from mongoengine import DoesNotExist

        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Grant not found: unknown"):
            GrantService.add_signature(said="unknown", signature="sig")

    # ==========================================================================
    # remove_signature tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_remove_signature_success(self, mock_objects):
        """Test that remove_signature removes a signature from the list"""
        mock_grant = Mock()
        mock_grant.signatures = ["sig1", "sig2", "sig3"]
        mock_objects.get.return_value = mock_grant

        result = GrantService.remove_signature(
            said="EGrantSAID123",
            signature="sig2",
        )

        assert "sig2" not in mock_grant.signatures
        assert mock_grant.signatures == ["sig1", "sig3"]
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_remove_signature_updates_timestamp(self, mock_objects):
        """Test that remove_signature updates the updated_at timestamp"""
        mock_grant = Mock()
        mock_grant.signatures = ["sig1"]
        old_timestamp = datetime(2024, 1, 1)
        mock_grant.updated_at = old_timestamp
        mock_objects.get.return_value = mock_grant

        GrantService.remove_signature(said="EGrantSAID123", signature="sig1")

        assert mock_grant.updated_at != old_timestamp

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_remove_signature_raises_not_found_when_grant_missing(self, mock_objects):
        """Test that remove_signature raises NotFoundError when grant is missing"""
        from mongoengine import DoesNotExist

        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Grant not found: unknown"):
            GrantService.remove_signature(said="unknown", signature="sig")

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_remove_signature_raises_not_found_when_signature_missing(
        self, mock_objects
    ):
        """Test that remove_signature raises NotFoundError when signature is not in list"""
        mock_grant = Mock()
        mock_grant.signatures = ["sig1", "sig2"]
        mock_objects.get.return_value = mock_grant

        with pytest.raises(NotFoundError, match="Signature not found in grant"):
            GrantService.remove_signature(said="EGrantSAID123", signature="nonexistent")

    # ==========================================================================
    # delete_grant tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_delete_grant_success(self, mock_objects):
        """Test that delete_grant successfully deletes a grant"""
        mock_grant = Mock()
        mock_objects.get.return_value = mock_grant

        GrantService.delete_grant("EGrantSAID123")

        mock_objects.get.assert_called_once_with(said="EGrantSAID123")
        mock_grant.delete.assert_called_once()

    @patch("castellan.core.services.grant_service.Grant.objects")
    def test_delete_grant_raises_not_found_error(self, mock_objects):
        """Test that delete_grant raises NotFoundError when grant doesn't exist"""
        from mongoengine import DoesNotExist

        mock_objects.get.side_effect = DoesNotExist()

        with pytest.raises(NotFoundError, match="Grant not found: unknown"):
            GrantService.delete_grant("unknown")

    # ==========================================================================
    # capture_grant tests
    # ==========================================================================

    @patch("castellan.core.services.grant_service.Grant")
    @patch("castellan.core.services.grant_service.helping")
    def test_capture_grant_success(self, mock_helping, mock_grant_cls):
        """Test that capture_grant captures a grant from hby database"""
        # Set up mock serder
        mock_serder = Mock()
        mock_serder.said = "EGrantSAID123"
        mock_serder.ked = {"r": "/ipex/grant", "data": "test"}
        self.mock_hby.db.exns.get.return_value = mock_serder

        # Set up mock for esigs iteration
        mock_prefixer = Mock()
        mock_prefixer.qb64 = "EPrefix123"
        mock_seqner = Mock()
        mock_seqner.qb64 = "0AAAA"
        mock_saider = Mock()
        mock_saider.qb64 = "ESaid123"
        mock_helping.klasify.return_value = (mock_prefixer, mock_seqner, mock_saider)

        mock_siger = Mock()
        mock_siger.qb64 = "AASignature123"
        self.mock_hby.db.esigs.getItemIter.return_value = [
            (("EGrantSAID123", "extra_key"), mock_siger)
        ]

        # Set up mock for ecigs
        mock_cigar = Mock()
        mock_cigar.verfer = Mock()
        mock_cigar.verfer.qb64 = "DVerfer123"
        mock_cigar.qb64 = "0BCigar123"
        self.mock_hby.db.ecigs.get.return_value = [mock_cigar]

        # Set up mock for epath
        self.mock_hby.db.epath.get.return_value = ["-pathed-data-"]

        # Set up mock Grant instance
        mock_grant = Mock()
        mock_grant_cls.return_value = mock_grant

        result = self.service.capture_grant("EGrantSAID123")

        self.mock_hby.db.exns.get.assert_called_once_with(keys=("EGrantSAID123",))
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    def test_capture_grant_raises_value_error_when_not_found(self):
        """Test that capture_grant raises ValueError when grant said is not saved"""
        self.mock_hby.db.exns.get.return_value = None

        with pytest.raises(ValueError, match="invalid grant said"):
            self.service.capture_grant("unknown")

    def test_capture_grant_raises_value_error_when_not_ipex_grant(self):
        """Test that capture_grant raises ValueError when serder is not an IPEX grant"""
        mock_serder = Mock()
        mock_serder.ked = {"r": "/other/route"}
        self.mock_hby.db.exns.get.return_value = mock_serder

        with pytest.raises(ValueError, match="not an IPEX grant"):
            self.service.capture_grant("EGrantSAID123")

    @patch("castellan.core.services.grant_service.Grant")
    @patch("castellan.core.services.grant_service.helping")
    def test_capture_grant_with_no_signatures(self, mock_helping, mock_grant_cls):
        """Test that capture_grant works with no signatures"""
        mock_serder = Mock()
        mock_serder.said = "EGrantSAID123"
        mock_serder.ked = {"r": "/ipex/grant"}
        self.mock_hby.db.exns.get.return_value = mock_serder

        # No signatures
        self.mock_hby.db.esigs.getItemIter.return_value = []

        # No cigars
        self.mock_hby.db.ecigs.get.return_value = []

        # No pathed data
        self.mock_hby.db.epath.get.return_value = []

        mock_grant = Mock()
        mock_grant_cls.return_value = mock_grant

        result = self.service.capture_grant("EGrantSAID123")

        mock_grant_cls.assert_called_once()
        call_kwargs = mock_grant_cls.call_args
        assert call_kwargs.kwargs["said"] == "EGrantSAID123"
        assert call_kwargs.kwargs["tsgs"] is None
        assert call_kwargs.kwargs["cigs"] == []
        mock_grant.save.assert_called_once()
        assert result == mock_grant

    @patch("castellan.core.services.grant_service.Grant")
    @patch("castellan.core.services.grant_service.helping")
    def test_capture_grant_with_multiple_signatures(self, mock_helping, mock_grant_cls):
        """Test that capture_grant handles multiple signatures"""
        mock_serder = Mock()
        mock_serder.said = "EGrantSAID123"
        mock_serder.ked = {"r": "/ipex/grant"}
        self.mock_hby.db.exns.get.return_value = mock_serder

        # Set up mock for multiple esigs
        mock_prefixer = Mock()
        mock_prefixer.qb64 = "EPrefix123"
        mock_seqner = Mock()
        mock_seqner.qb64 = "0AAAA"
        mock_saider = Mock()
        mock_saider.qb64 = "ESaid123"
        mock_helping.klasify.return_value = (mock_prefixer, mock_seqner, mock_saider)

        mock_siger1 = Mock()
        mock_siger1.qb64 = "AASig1"
        mock_siger2 = Mock()
        mock_siger2.qb64 = "AASig2"
        self.mock_hby.db.esigs.getItemIter.return_value = [
            (("EGrantSAID123", "key1"), mock_siger1),
            (("EGrantSAID123", "key2"), mock_siger2),
        ]

        self.mock_hby.db.ecigs.get.return_value = []
        self.mock_hby.db.epath.get.return_value = []

        mock_grant = Mock()
        mock_grant_cls.return_value = mock_grant

        result = self.service.capture_grant("EGrantSAID123")

        mock_grant.save.assert_called_once()
        assert result == mock_grant
