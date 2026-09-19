# -*- encoding: utf-8 -*-
from unittest.mock import Mock

import falcon
import pytest

from castellan.app.api.account import AccountCollectionEnd, AccountResourceEnd
from castellan.core.services.custom.custom_errors import NotFoundError


class TestAccountCollectionEnd:
    """Test suite for AccountCollectionEnd (GET /account)"""

    def setup_method(self):
        self.service = Mock()
        self.end = AccountCollectionEnd(self.service)
        self.req = Mock()

    def test_on_get_returns_accounts(self):
        """Test GET /account returns list of accounts"""
        mock_account1 = Mock()
        mock_account1.aid = "EAccount1AID"
        mock_account1.username = "alice"
        mock_account1.email = "alice@example.com"
        mock_account1.first_name = "Alice"
        mock_account1.last_name = "Smith"
        mock_account1.role = "Owner"
        mock_account1.key_state = {"sn": 0}
        mock_account1.created_at = None

        mock_account2 = Mock()
        mock_account2.aid = "EAccount2AID"
        mock_account2.username = "bob"
        mock_account2.email = "bob@example.com"
        mock_account2.first_name = "Bob"
        mock_account2.last_name = "Jones"
        mock_account2.role = "Member"
        mock_account2.key_state = {"sn": 1}
        mock_account2.created_at = None

        self.service.list_accounts.return_value = ([mock_account1, mock_account2], 2, 1)
        self.req.get_param.return_value = None
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
            "accounts": [
                {
                    "aid": "EAccount1AID",
                    "username": "alice",
                    "email": "alice@example.com",
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "role": "Owner",
                    "key_state": {"sn": 0},
                    "created_at": None,
                },
                {
                    "aid": "EAccount2AID",
                    "username": "bob",
                    "email": "bob@example.com",
                    "first_name": "Bob",
                    "last_name": "Jones",
                    "role": "Member",
                    "key_state": {"sn": 1},
                    "created_at": None,
                },
            ],
        }

    def test_on_get_returns_empty_list(self):
        """Test GET /account returns empty list when no accounts exist"""
        self.service.list_accounts.return_value = ([], 0, 1)
        self.req.get_param.return_value = None
        self.req.get_param_as_int.side_effect = lambda k, default: default
        self.req.get_param_as_list.return_value = None
        resp = Mock()

        self.end.on_get(self.req, resp)

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json"
        assert resp.media == {"count": 0, "page": 0, "num_pages": 1, "accounts": []}

    def test_on_get_handles_optional_fields(self):
        """Test GET /account handles accounts with missing optional fields"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        mock_account.username = "testuser"
        mock_account.email = None
        mock_account.first_name = None
        mock_account.last_name = None
        mock_account.role = None
        mock_account.key_state = None
        mock_account.created_at = None

        self.service.list_accounts.return_value = ([mock_account], 1, 1)
        self.req.get_param.return_value = None
        self.req.get_param_as_int.side_effect = lambda k, default: default
        self.req.get_param_as_list.return_value = None
        resp = Mock()

        self.end.on_get(self.req, resp)

        assert resp.status == falcon.HTTP_200
        assert resp.media == {
            "count": 1,
            "page": 0,
            "num_pages": 1,
            "accounts": [
                {
                    "aid": "EAccountAID",
                    "username": "testuser",
                    "email": "",
                    "first_name": "",
                    "last_name": "",
                    "role": "Owner",
                    "key_state": None,
                    "created_at": None,
                }
            ],
        }

    def test_on_get_handles_service_error(self):
        """Test GET /account handles service errors"""
        self.service.list_accounts.side_effect = Exception("Database error")
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_get(self.req, resp)


class TestAccountResourceEnd:
    """Test suite for AccountResourceEnd (POST /accounts/{aid} and DELETE /accounts/{aid})"""

    def setup_method(self):
        self.service = Mock()
        self.end = AccountResourceEnd(self.service)
        self.req = Mock()

    def test_on_post_updates_account(self):
        """Test POST /accounts/{aid} updates account successfully"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        mock_account.username = "alice"
        mock_account.email = "alice@updated.com"
        mock_account.first_name = "Alice"
        mock_account.last_name = "Updated"
        mock_account.key_state = {"sn": 0}
        mock_account.created_at = None

        self.service.update_account.return_value = mock_account
        self.req.media = {
            "email": "alice@updated.com",
            "last_name": "Updated",
        }
        resp = Mock()

        self.end.on_post(self.req, resp, "EAccountAID")

        assert resp.status == falcon.HTTP_200
        assert resp.content_type == "application/json"
        assert resp.media["email"] == "alice@updated.com"
        assert resp.media["last_name"] == "Updated"
        self.service.update_account.assert_called_once_with(
            "EAccountAID", {"email": "alice@updated.com", "last_name": "Updated"}
        )

    def test_on_post_filters_aid_and_kel(self):
        """Test POST /accounts/{aid} filters out aid and kel from update data"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        mock_account.username = "alice"
        mock_account.email = "alice@example.com"
        mock_account.first_name = "Alice"
        mock_account.last_name = "Smith"
        mock_account.key_state = {"sn": 0}
        mock_account.created_at = None

        self.service.update_account.return_value = mock_account
        self.req.media = {
            "aid": "ENewAID",  # Should be filtered out
            "kel": "new-kel-data",  # Should be filtered out
            "email": "alice@updated.com",
        }
        resp = Mock()

        self.end.on_post(self.req, resp, "EAccountAID")

        # Verify aid and kel were filtered out
        self.service.update_account.assert_called_once_with(
            "EAccountAID", {"email": "alice@updated.com"}
        )
        assert resp.status == falcon.HTTP_200

    def test_on_post_returns_400_when_body_empty(self):
        """Test POST /accounts/{aid} returns 400 when request body is empty"""
        self.req.media = None
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp, "EAccountAID")

    def test_on_post_returns_400_when_no_updatable_fields(self):
        """Test POST /accounts/{aid} returns 400 when only aid/kel provided"""
        self.req.media = {
            "aid": "ENewAID",
            "kel": "new-kel-data",
        }
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp, "EAccountAID")

    def test_on_post_returns_404_when_account_not_found(self):
        """Test POST /accounts/{aid} returns 404 when account doesn't exist"""
        self.service.update_account.side_effect = NotFoundError(
            "Account not found: EUNKNOWN"
        )
        self.req.media = {"email": "test@example.com"}
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_post(self.req, resp, "EUNKNOWN")

    def test_on_post_returns_400_for_validation_error(self):
        """Test POST /accounts/{aid} returns 400 for validation errors"""
        self.service.update_account.side_effect = ValueError(
            "There must be at least one role 'Owner' account"
        )
        self.req.media = {"role": "member"}
        resp = Mock()

        with pytest.raises(falcon.HTTPBadRequest):
            self.end.on_post(self.req, resp, "EAccountAID")

    def test_on_post_handles_no_changes(self):
        """Test POST /accounts/{aid} handles case when update_account returns None"""
        mock_account = Mock()
        mock_account.aid = "EAccountAID"
        mock_account.username = "alice"
        mock_account.email = "alice@example.com"
        mock_account.first_name = "Alice"
        mock_account.last_name = "Smith"
        mock_account.key_state = {"sn": 0}
        mock_account.created_at = None

        # update_account returns None when no changes made
        self.service.update_account.return_value = None
        # get_account returns the current account
        self.service.get_account.return_value = mock_account
        self.req.media = {"email": "alice@example.com"}  # Same value, no change
        resp = Mock()

        self.end.on_post(self.req, resp, "EAccountAID")

        assert resp.status == falcon.HTTP_200
        assert resp.media["email"] == "alice@example.com"
        self.service.get_account.assert_called_once_with("EAccountAID")

    def test_on_post_handles_service_error(self):
        """Test POST /accounts/{aid} handles service errors"""
        self.service.update_account.side_effect = Exception("Database error")
        self.req.media = {"email": "test@example.com"}
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_post(self.req, resp, "EAccountAID")

    def test_on_delete_deletes_account(self):
        """Test DELETE /accounts/{aid} deletes account successfully"""
        resp = Mock()

        self.end.on_delete(self.req, resp, "EAccountAID")

        assert resp.status == falcon.HTTP_204
        self.service.delete_account.assert_called_once_with("EAccountAID")

    def test_on_delete_returns_404_when_account_not_found(self):
        """Test DELETE /accounts/{aid} returns 404 when account doesn't exist"""
        self.service.delete_account.side_effect = NotFoundError(
            "Account not found: EUNKNOWN"
        )
        resp = Mock()

        with pytest.raises(falcon.HTTPNotFound):
            self.end.on_delete(self.req, resp, "EUNKNOWN")

    def test_on_delete_handles_service_error(self):
        """Test DELETE /accounts/{aid} handles service errors"""
        self.service.delete_account.side_effect = Exception("Database error")
        resp = Mock()

        with pytest.raises(falcon.HTTPInternalServerError):
            self.end.on_delete(self.req, resp, "EAccountAID")
