# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch
import pytest

from castellan.core.services.account_service import AccountService
from castellan.core.services.custom.custom_errors import ConflictError, NotFoundError


class TestAccount:
    """Test suite for Account model"""

    @patch("castellan.core.services.account_service.Account.objects")
    def test_account_exists_returns_true_when_account_found(self, mock_objects):
        """Test that account_exists returns True when account is found"""
        mock_objects.return_value.count.return_value = 1

        result = AccountService.account_exists("test_aid")

        assert result is True
        mock_objects.assert_called_once_with(aid="test_aid")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_account_exists_returns_false_when_account_not_found(self, mock_objects):
        """Test that account_exists returns False when account is not found"""
        mock_objects.return_value.count.return_value = 0

        result = AccountService.account_exists("nonexistent_aid")

        assert result is False
        mock_objects.assert_called_once_with(aid="nonexistent_aid")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_account_exists_raises_runtime_error_on_exception(self, mock_objects):
        """Test that account_exists raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(
            RuntimeError, match="An error occurred while querying account"
        ):
            AccountService.account_exists("test_aid")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_returns_account_when_found(self, mock_objects):
        """Test that get_account returns account when found"""
        mock_account = Mock()
        mock_objects.return_value.first.return_value = mock_account

        result = AccountService.get_account("test_aid")

        assert result == mock_account
        mock_objects.assert_called_once_with(aid="test_aid")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_returns_none_when_not_found(self, mock_objects):
        """Test that get_account returns None when not found"""
        mock_objects.return_value.first.return_value = None

        result = AccountService.get_account("nonexistent_aid")

        assert result is None

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_returns_none_on_exception(self, mock_objects):
        """Test that get_account returns None on exception"""
        mock_objects.side_effect = Exception("Database error")

        result = AccountService.get_account("test_aid")

        assert result is None

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_username_returns_account(self, mock_objects):
        """Test that get_account_by_username returns account when found"""
        mock_account = Mock()
        mock_objects.return_value = [mock_account]

        result = AccountService.get_account_by_username("testuser")

        assert result == mock_account
        mock_objects.assert_called_once_with(username="testuser")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_username_returns_none_when_not_found(self, mock_objects):
        """Test that get_account_by_username returns None when not found"""
        mock_objects.return_value = []

        result = AccountService.get_account_by_username("nonexistent")

        assert result is None

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_username_raises_conflict_error_on_multiple_results(
        self, mock_objects
    ):
        """Test that get_account_by_username raises ConflictError when multiple accounts found"""
        mock_account1 = Mock()
        mock_account2 = Mock()
        mock_objects.return_value = [mock_account1, mock_account2]

        with pytest.raises(
            ConflictError,
            match="More than one Account returned for the given username: duplicate'",
        ):
            AccountService.get_account_by_username("duplicate")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_username_raises_runtime_error_on_exception(
        self, mock_objects
    ):
        """Test that get_account_by_username raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying account"):
            AccountService.get_account_by_username("testuser")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_email_returns_account(self, mock_objects):
        """Test that get_account_by_email returns account when found"""
        mock_account = Mock()
        mock_objects.return_value = [mock_account]

        result = AccountService.get_account_by_email("test@example.com")

        assert result == mock_account
        mock_objects.assert_called_once_with(email="test@example.com")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_email_returns_none_when_not_found(self, mock_objects):
        """Test that get_account_by_email returns None when not found"""
        mock_objects.return_value = []

        result = AccountService.get_account_by_email("nonexistent@example.com")

        assert result is None

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_email_raises_conflict_error_on_multiple_results(
        self, mock_objects
    ):
        """Test that get_account_by_email raises ConflictError when multiple accounts found"""
        mock_account1 = Mock()
        mock_account2 = Mock()
        mock_objects.return_value = [mock_account1, mock_account2]

        with pytest.raises(ConflictError, match="More than one Account returned"):
            AccountService.get_account_by_email("duplicate@example.com")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_get_account_by_email_raises_runtime_error_on_exception(self, mock_objects):
        """Test that get_account_by_email raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying account"):
            AccountService.get_account_by_email("test@example.com")

    @patch("castellan.core.services.account_service.Account.objects")
    def test_list_accounts_returns_all_accounts(self, mock_objects):
        """Test that list_accounts returns all accounts"""
        mock_account1 = Mock()
        mock_account2 = Mock()
        mock_objects.all.return_value = [mock_account1, mock_account2]

        result = AccountService.list_accounts()

        assert result == [mock_account1, mock_account2]
        mock_objects.all.assert_called_once()

    @patch("castellan.core.services.account_service.Account.objects")
    def test_list_accounts_raises_runtime_error_on_exception(self, mock_objects):
        """Test that list_accounts raises RuntimeError on exception"""
        mock_objects.all.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying accounts"):
            AccountService.list_accounts()

    @patch("castellan.core.services.account_service.Account.objects")
    def test_count_accounts_returns_count(self, mock_objects):
        """Test that count_accounts returns correct count"""
        mock_objects.count.return_value = 5

        result = AccountService.count_accounts()

        assert result == 5
        mock_objects.count.assert_called_once()

    @patch("castellan.core.services.account_service.Account.objects")
    def test_count_accounts_raises_runtime_error_on_exception(self, mock_objects):
        """Test that count_accounts raises RuntimeError on exception"""
        mock_objects.count.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying accounts"):
            AccountService.count_accounts()

    @patch("castellan.core.services.account_service.Account.objects")
    def test_async_list_accounts_returns_filtered_accounts(self, mock_objects):
        """Test that async_list_accounts returns accounts modified after date"""
        mock_account1 = Mock()
        mock_account2 = Mock()
        timestamp = 1234567890
        mock_objects.return_value = [mock_account1, mock_account2]

        result = AccountService.async_list_accounts(timestamp)

        assert result == [mock_account1, mock_account2]
        mock_objects.assert_called_once_with(lastModified__gt=timestamp)

    @patch("castellan.core.services.account_service.Account.objects")
    def test_async_list_accounts_raises_runtime_error_on_exception(self, mock_objects):
        """Test that async_list_accounts raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying accounts"):
            AccountService.async_list_accounts(1234567890)


class TestAccountService:
    """Test suite for AccountService class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.service = AccountService(self.mock_parser, self.mock_kvy)

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    @patch("castellan.core.services.account_service.datetime")
    @patch("castellan.core.services.account_service.asdict")
    def test_create_account_success(
        self, mock_asdict, mock_datetime, mock_account_exists, mock_account_class
    ):
        """Test successful account creation"""
        mock_account_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_account = Mock()
        mock_account_class.return_value = mock_account

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        mock_asdict.return_value = {"key": "value"}

        doc = {"aid": "test_aid", "username": "testuser", "email": "test@example.com"}
        kel = b"test_kel_data"

        result = self.service.create_account(doc, kel)

        assert result == mock_account
        assert mock_account.lastModified == 1234567890
        assert mock_account.kel == "test_kel_data"
        assert mock_account.key_state == {"key": "value"}
        mock_account.save.assert_called_once()
        self.mock_parser.parse.assert_called_once_with(
            ims=bytearray(kel), kvy=self.mock_kvy, local=True
        )

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    def test_create_account_raises_conflict_error_when_account_exists(
        self, mock_account_exists, mock_account_class
    ):
        """Test that create_account raises ConflictError when account already exists"""
        mock_account_exists.return_value = True
        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account_class.return_value = mock_account

        doc = {"aid": "test_aid", "username": "testuser"}
        kel = b"test_kel_data"

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_account(doc, kel)

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    def test_create_account_raises_runtime_error_on_parse_failure(
        self, mock_account_exists, mock_account_class
    ):
        """Test that create_account raises RuntimeError when parsing fails"""
        mock_account_exists.return_value = False
        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account_class.return_value = mock_account

        self.mock_parser.parse.side_effect = Exception("Parse error")

        doc = {"aid": "test_aid", "username": "testuser"}
        kel = b"test_kel_data"

        with pytest.raises(RuntimeError, match="parsing kel into Kevery"):
            self.service.create_account(doc, kel)

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    def test_create_account_raises_runtime_error_when_aid_not_in_kevers(
        self, mock_account_exists, mock_account_class
    ):
        """Test that create_account raises RuntimeError when aid not in kevers"""
        mock_account_exists.return_value = False
        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account_class.return_value = mock_account

        self.mock_kvy.kevers = {}

        doc = {"aid": "test_aid", "username": "testuser"}
        kel = b"test_kel_data"

        with pytest.raises(
            RuntimeError, match="parsing kel into Kevery for aid=test_aid"
        ):
            self.service.create_account(doc, kel)

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    @patch("castellan.core.services.account_service.datetime")
    @patch("castellan.core.services.account_service.asdict")
    def test_create_account_raises_runtime_error_on_save_failure(
        self, mock_asdict, mock_datetime, mock_account_exists, mock_account_class
    ):
        """Test that create_account raises RuntimeError when save fails"""
        mock_account_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_account = Mock()
        mock_account_class.return_value = mock_account
        mock_account.save.side_effect = Exception("Save error")

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        mock_asdict.return_value = {"key": "value"}

        doc = {"aid": "test_aid", "username": "testuser"}
        kel = b"test_kel_data"

        with pytest.raises(RuntimeError, match="saving account"):
            self.service.create_account(doc, kel)

    @patch.object(AccountService, "get_account")
    def test_get_account_by_aid_returns_none_when_not_found(self, mock_get_account):
        """Test that get_account_by_aid returns None when not found"""
        mock_get_account.return_value = None

        result = self.service.get_account_by_aid("nonexistent_aid")

        assert result is None

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_updates_fields(self, mock_datetime, mock_get_account):
        """Test that update_account updates account fields"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account.username = "oldusername"
        mock_account.email = "old@example.com"
        mock_get_account.return_value = mock_account

        doc = {
            "username": "newusername",
            "email": "new@example.com",
            "first_name": "John",
        }

        result = self.service.update_account("test_aid", doc)

        assert mock_account.lastModified == 9876543210
        assert mock_account.username == "newusername"
        assert mock_account.email == "new@example.com"
        assert mock_account.first_name == "John"
        mock_account.save.assert_called_once()
        assert result == mock_account

    @patch.object(AccountService, "get_account")
    def test_update_account_raises_not_found_error_when_account_not_found(
        self, mock_get_account
    ):
        """Test that update_account raises NotFoundError when account not found"""
        mock_get_account.return_value = None

        doc = {"username": "newusername"}

        with pytest.raises(NotFoundError, match="Account not found"):
            self.service.update_account("nonexistent_aid", doc)

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_skips_aid_field(self, mock_datetime, mock_get_account):
        """Test that update_account skips updating aid field"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_get_account.return_value = mock_account

        doc = {"aid": "new_aid", "username": "newusername"}

        self.service.update_account("test_aid", doc)

        assert mock_account.aid == "test_aid"
        assert mock_account.username == "newusername"

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_with_kel(self, mock_datetime, mock_get_account):
        """Test that update_account processes KEL correctly"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_get_account.return_value = mock_account

        mock_serder_before = Mock()
        mock_serder_before.sn = 1
        mock_serder_after = Mock()
        mock_serder_after.sn = 2

        mock_kever = Mock()
        mock_kever.serder = mock_serder_before
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        def update_serder(*args, **kwargs):
            mock_kever.serder = mock_serder_after

        self.mock_parser.parse.side_effect = update_serder

        mock_state = Mock()
        mock_state.dict.return_value = {"new": "state"}
        mock_kever.state.return_value = mock_state

        doc = {"username": "newusername"}
        kel = b"new_kel_data"

        self.service.update_account("test_aid", doc, kel)

        assert mock_account.kel == "new_kel_data"
        assert mock_account.key_state == {"new": "state"}
        mock_account.save.assert_called_once()
        self.mock_parser.parse.assert_called_once_with(
            ims=bytearray(kel), kvy=self.mock_kvy, local=True
        )

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_with_kel_raises_runtime_error_on_parse_failure(
        self, mock_datetime, mock_get_account
    ):
        """Test that update_account raises RuntimeError when KEL parsing fails"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_get_account.return_value = mock_account

        mock_serder = Mock()
        mock_serder.sn = 1
        mock_kever = Mock()
        mock_kever.serder = mock_serder
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        self.mock_parser.parse.side_effect = Exception("Parse error")

        doc = {"username": "newusername"}
        kel = b"bad_kel_data"

        with pytest.raises(RuntimeError, match="parsing kel into Kevery"):
            self.service.update_account("test_aid", doc, kel)

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_does_not_update_if_kel_sn_not_increased(
        self, mock_datetime, mock_get_account
    ):
        """Test that update_account does not update KEL if sequence number not increased"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account.kel = "old_kel"
        mock_account.key_state = {"old": "state"}
        mock_get_account.return_value = mock_account

        mock_serder = Mock()
        mock_serder.sn = 5
        mock_kever = Mock()
        mock_kever.serder = mock_serder
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        doc = {}
        kel = b"same_kel_data"

        result = self.service.update_account("test_aid", doc, kel)

        assert result is None
        assert mock_account.kel == "old_kel"
        assert mock_account.key_state == {"old": "state"}
        mock_account.save.assert_not_called()

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_returns_none_when_no_updates(
        self, mock_datetime, mock_get_account
    ):
        """Test that update_account returns None when no fields are updated"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_get_account.return_value = mock_account

        doc = {}

        result = self.service.update_account("test_aid", doc)

        assert result is None
        mock_account.save.assert_not_called()

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_ignores_nonexistent_fields(
        self, mock_datetime, mock_get_account
    ):
        """Test that update_account ignores fields that don't exist on account"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock(spec=["aid", "username", "email", "lastModified", "save"])
        mock_account.aid = "test_aid"
        mock_account.username = "oldusername"
        mock_get_account.return_value = mock_account

        doc = {"username": "newusername", "nonexistent_field": "value"}

        self.service.update_account("test_aid", doc)

        assert mock_account.username == "newusername"
        mock_account.save.assert_called_once()

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_raises_runtime_error_on_save_failure(
        self, mock_datetime, mock_get_account
    ):
        """Test that update_account raises RuntimeError when save fails"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account.username = "oldusername"
        mock_account.save.side_effect = Exception("Save error")
        mock_get_account.return_value = mock_account

        doc = {"username": "newusername"}

        with pytest.raises(RuntimeError, match="Error .* updating account"):
            self.service.update_account("test_aid", doc)

    @patch("castellan.core.services.account_service.Account.objects")
    def test_delete_account(self, mock_objects):
        """Test that delete_account deletes the account"""
        mock_query = Mock()
        mock_objects.return_value = mock_query

        self.service.delete_account("test_aid")

        mock_objects.assert_called_once_with(aid="test_aid")
        mock_query.delete.assert_called_once()

    @patch("castellan.core.services.account_service.Account.objects")
    def test_delete_account_with_nonexistent_account(self, mock_objects):
        """Test that delete_account handles nonexistent account gracefully"""
        mock_query = Mock()
        mock_objects.return_value = mock_query

        self.service.delete_account("nonexistent_aid")

        mock_objects.assert_called_once_with(aid="nonexistent_aid")
        mock_query.delete.assert_called_once()


class TestAccountServiceIntegration:
    """Integration tests for AccountService with realistic scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.service = AccountService(self.mock_parser, self.mock_kvy)

    @patch("castellan.core.services.account_service.Account")
    @patch("castellan.core.services.account_service.AccountService.account_exists")
    @patch("castellan.core.services.account_service.datetime")
    @patch("castellan.core.services.account_service.asdict")
    def test_create_account_full_workflow(
        self, mock_asdict, mock_datetime, mock_account_exists, mock_account_class
    ):
        """Test complete workflow of creating an account"""
        mock_account_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_account = Mock()
        mock_account_class.return_value = mock_account

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        mock_asdict.return_value = {"i": "test_aid", "s": "0", "d": "digest"}

        doc = {
            "aid": "test_aid",
            "username": "john_doe",
            "email": "john@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        kel = b"-----BEGIN KERI KEY EVENT LOG-----\ntest_kel_data\n-----END KERI KEY EVENT LOG-----"

        result = self.service.create_account(doc, kel)

        assert result == mock_account
        assert mock_account.lastModified == 1234567890
        assert (
            mock_account.kel
            == "-----BEGIN KERI KEY EVENT LOG-----\ntest_kel_data\n-----END KERI KEY EVENT LOG-----"
        )
        assert mock_account.key_state == {"i": "test_aid", "s": "0", "d": "digest"}

        self.mock_parser.parse.assert_called_once()
        call_args = self.mock_parser.parse.call_args
        assert call_args[1]["kvy"] == self.mock_kvy
        assert call_args[1]["local"] is True

        mock_account.save.assert_called_once()

    @patch.object(AccountService, "get_account")
    @patch("castellan.core.services.account_service.datetime")
    def test_update_account_full_workflow_with_kel_update(
        self, mock_datetime, mock_get_account
    ):
        """Test complete workflow of updating an account with KEL rotation"""
        mock_datetime.datetime.now.return_value.timestamp.return_value = 9876543210

        mock_account = Mock()
        mock_account.aid = "test_aid"
        mock_account.username = "john_doe"
        mock_account.email = "john@example.com"
        mock_account.kel = "old_kel_data"
        mock_account.key_state = {"i": "test_aid", "s": "0"}
        mock_get_account.return_value = mock_account

        mock_serder_before = Mock()
        mock_serder_before.sn = 0
        mock_serder_after = Mock()
        mock_serder_after.sn = 1

        mock_kever = Mock()
        mock_kever.serder = mock_serder_before
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        def update_serder_on_parse(*args, **kwargs):
            mock_kever.serder = mock_serder_after

        self.mock_parser.parse.side_effect = update_serder_on_parse

        mock_state = Mock()
        mock_state.dict.return_value = {"i": "test_aid", "s": "1", "k": ["new_key"]}
        mock_kever.state.return_value = mock_state

        doc = {
            "email": "newemail@example.com",
            "first_name": "John",
            "last_name": "Doe",
        }
        kel = b"new_kel_with_rotation"

        result = self.service.update_account("test_aid", doc, kel)

        assert result == mock_account
        assert mock_account.lastModified == 9876543210
        assert mock_account.email == "newemail@example.com"
        assert mock_account.first_name == "John"
        assert mock_account.last_name == "Doe"
        assert mock_account.kel == "new_kel_with_rotation"
        assert mock_account.key_state == {"i": "test_aid", "s": "1", "k": ["new_key"]}

        mock_account.save.assert_called_once()
        self.mock_parser.parse.assert_called_once()
