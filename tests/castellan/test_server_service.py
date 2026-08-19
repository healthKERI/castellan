# -*- encoding: utf-8 -*-
from unittest.mock import Mock, patch
import pytest

from castellan.core.services.server_service import ServerService
from castellan.core.services.custom.custom_errors import ConflictError


class TestServer:
    """Test suite for Server model static methods"""

    @patch("castellan.core.services.server_service.Server.objects")
    def test_server_exists_returns_true_when_server_found(self, mock_objects):
        """Test that server_exists returns True when server is found"""
        mock_objects.return_value.count.return_value = 1

        result = ServerService.server_exists("test_aid")

        assert result is True
        mock_objects.assert_called_once_with(aid="test_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_server_exists_returns_false_when_server_not_found(self, mock_objects):
        """Test that server_exists returns False when server is not found"""
        mock_objects.return_value.count.return_value = 0

        result = ServerService.server_exists("nonexistent_aid")

        assert result is False
        mock_objects.assert_called_once_with(aid="nonexistent_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_server_exists_raises_runtime_error_on_exception(self, mock_objects):
        """Test that server_exists raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(
            RuntimeError, match="An error occurred while querying server"
        ):
            ServerService.server_exists("test_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_returns_server_when_found(self, mock_objects):
        """Test that get_server returns server when found"""
        mock_server = Mock()
        mock_objects.return_value.first.return_value = mock_server

        result = ServerService.get_server("test_aid")

        assert result == mock_server
        mock_objects.assert_called_once_with(aid="test_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_returns_none_when_not_found(self, mock_objects):
        """Test that get_server returns None when not found"""
        mock_objects.return_value.first.return_value = None

        result = ServerService.get_server("nonexistent_aid")

        assert result is None

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_returns_none_on_exception(self, mock_objects):
        """Test that get_server returns None on exception"""
        mock_objects.side_effect = Exception("Database error")

        result = ServerService.get_server("test_aid")

        assert result is None

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_username_returns_server(self, mock_objects):
        """Test that get_server_by_username returns server when found"""
        mock_server = Mock()
        mock_objects.return_value = [mock_server]

        result = ServerService.get_server_by_username("testuser")

        assert result == mock_server
        mock_objects.assert_called_once_with(username="testuser")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_username_returns_none_when_not_found(self, mock_objects):
        """Test that get_server_by_username returns None when not found"""
        mock_objects.return_value = []

        result = ServerService.get_server_by_username("nonexistent")

        assert result is None

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_username_raises_conflict_error_on_multiple_results(
        self, mock_objects
    ):
        """Test that get_server_by_username raises ConflictError when multiple servers found"""
        mock_server1 = Mock()
        mock_server2 = Mock()
        mock_objects.return_value = [mock_server1, mock_server2]

        with pytest.raises(ConflictError, match="More than one Server returned"):
            ServerService.get_server_by_username("duplicate")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_username_raises_runtime_error_on_exception(
        self, mock_objects
    ):
        """Test that get_server_by_username raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying server"):
            ServerService.get_server_by_username("testuser")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_email_returns_server(self, mock_objects):
        """Test that get_server_by_email returns server when found"""
        mock_server = Mock()
        mock_objects.return_value = [mock_server]

        result = ServerService.get_server_by_email("test@example.com")

        assert result == mock_server
        mock_objects.assert_called_once_with(email="test@example.com")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_email_returns_none_when_not_found(self, mock_objects):
        """Test that get_server_by_email returns None when not found"""
        mock_objects.return_value = []

        result = ServerService.get_server_by_email("nonexistent@example.com")

        assert result is None

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_email_raises_conflict_error_on_multiple_results(
        self, mock_objects
    ):
        """Test that get_server_by_email raises ConflictError when multiple servers found"""
        mock_server1 = Mock()
        mock_server2 = Mock()
        mock_objects.return_value = [mock_server1, mock_server2]

        with pytest.raises(ConflictError, match="More than one Server returned"):
            ServerService.get_server_by_email("duplicate@example.com")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_email_raises_runtime_error_on_exception(self, mock_objects):
        """Test that get_server_by_email raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying server"):
            ServerService.get_server_by_email("test@example.com")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_list_servers_returns_all_servers(self, mock_objects):
        """Test that list_servers returns all servers"""
        mock_server1 = Mock()
        mock_server2 = Mock()
        mock_objects.all.return_value = [mock_server1, mock_server2]

        result = ServerService.list_servers()

        assert result == [mock_server1, mock_server2]
        mock_objects.all.assert_called_once()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_list_servers_raises_runtime_error_on_exception(self, mock_objects):
        """Test that list_servers raises RuntimeError on exception"""
        mock_objects.all.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying servers"):
            ServerService.list_servers()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_count_servers_returns_count(self, mock_objects):
        """Test that count_servers returns correct count"""
        mock_objects.count.return_value = 5

        result = ServerService.count_servers()

        assert result == 5
        mock_objects.count.assert_called_once()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_count_servers_raises_runtime_error_on_exception(self, mock_objects):
        """Test that count_servers raises RuntimeError on exception"""
        mock_objects.count.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying servers"):
            ServerService.count_servers()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_async_list_servers_returns_filtered_servers(self, mock_objects):
        """Test that async_list_servers returns servers modified after date"""
        timestamp = 1234567890
        mock_server1 = Mock()
        mock_server2 = Mock()
        mock_objects.return_value = [mock_server1, mock_server2]

        result = ServerService.async_list_servers(timestamp)

        assert result == [mock_server1, mock_server2]
        mock_objects.assert_called_once_with(lastModified__gt=timestamp)

    @patch("castellan.core.services.server_service.Server.objects")
    def test_async_list_servers_raises_runtime_error_on_exception(self, mock_objects):
        """Test that async_list_servers raises RuntimeError on exception"""
        mock_objects.side_effect = Exception("Database error")

        with pytest.raises(RuntimeError, match="An error occurred querying servers"):
            ServerService.async_list_servers(1234567890)


class TestServerService:
    """Test suite for ServerService class instance methods"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_kel_service = Mock()
        self.service = ServerService(
            self.mock_parser, self.mock_kvy, self.mock_kel_service
        )

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    @patch("castellan.core.services.server_service.datetime")
    @patch("castellan.core.services.server_service.asdict")
    def test_create_server_success(
        self, mock_asdict, mock_datetime, mock_server_exists, mock_server_class
    ):
        """Test successful server creation"""
        mock_server_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_server = Mock()
        mock_server_class.return_value = mock_server

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        mock_asdict.return_value = {"i": "test_aid", "s": "0"}

        doc = {"aid": "test_aid", "ipaddress": "192.168.1.1", "port": 8080}
        kel = b"test_kel_data"

        result = self.service.create_server(doc, kel)

        assert result == mock_server
        assert mock_server.lastModified == 1234567890
        assert mock_server.kel == "test_kel_data"
        assert mock_server.key_state == {"i": "test_aid", "s": "0"}
        mock_server.save.assert_called_once()
        self.mock_parser.parse.assert_called_once_with(
            ims=bytearray(kel), kvy=self.mock_kvy, local=True
        )
        self.mock_kel_service.capture_kel.assert_called_once_with("test_aid")
        self.mock_kel_service.capture_rpys.assert_called_once_with("test_aid")

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    def test_create_server_raises_conflict_error_when_server_exists(
        self, mock_server_exists, mock_server_class
    ):
        """Test that create_server raises ConflictError when server already exists"""
        mock_server_exists.return_value = True
        mock_server = Mock()
        mock_server.aid = "test_aid"
        mock_server_class.return_value = mock_server

        doc = {"aid": "test_aid", "ipaddress": "192.168.1.1", "port": 8080}
        kel = b"test_kel_data"

        with pytest.raises(ConflictError, match="already exists"):
            self.service.create_server(doc, kel)

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    def test_create_server_raises_runtime_error_on_parse_failure(
        self, mock_server_exists, mock_server_class
    ):
        """Test that create_server raises RuntimeError when parsing fails"""
        mock_server_exists.return_value = False
        mock_server = Mock()
        mock_server.aid = "test_aid"
        mock_server_class.return_value = mock_server

        self.mock_parser.parse.side_effect = Exception("Parse error")

        doc = {"aid": "test_aid", "ipaddress": "192.168.1.1", "port": 8080}
        kel = b"test_kel_data"

        with pytest.raises(RuntimeError, match="parsing kel into Kevery"):
            self.service.create_server(doc, kel)

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    def test_create_server_raises_runtime_error_when_aid_not_in_kevers(
        self, mock_server_exists, mock_server_class
    ):
        """Test that create_server raises RuntimeError when aid not in kevers"""
        mock_server_exists.return_value = False
        mock_server = Mock()
        mock_server.aid = "test_aid"
        mock_server_class.return_value = mock_server

        self.mock_kvy.kevers = {}

        doc = {"aid": "test_aid", "ipaddress": "192.168.1.1", "port": 8080}
        kel = b"test_kel_data"

        with pytest.raises(
            RuntimeError, match="parsing kel into Kevery for aid=test_aid"
        ):
            self.service.create_server(doc, kel)

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    @patch("castellan.core.services.server_service.datetime")
    @patch("castellan.core.services.server_service.asdict")
    def test_create_server_raises_runtime_error_on_save_failure(
        self, mock_asdict, mock_datetime, mock_server_exists, mock_server_class
    ):
        """Test that create_server raises RuntimeError when save fails"""
        mock_server_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_server = Mock()
        mock_server_class.return_value = mock_server
        mock_server.save.side_effect = Exception("Save error")

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"test_aid": mock_kever}

        mock_asdict.return_value = {"i": "test_aid", "s": "0"}

        doc = {"aid": "test_aid", "ipaddress": "192.168.1.1", "port": 8080}
        kel = b"test_kel_data"

        with pytest.raises(RuntimeError, match="saving server"):
            self.service.create_server(doc, kel)

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_aid_returns_server(self, mock_objects):
        """Test that get_server_by_aid returns server"""
        mock_server = Mock()
        mock_objects.return_value.first.return_value = mock_server

        result = self.service.get_server_by_aid("test_aid")

        assert result == mock_server
        mock_objects.assert_called_once_with(aid="test_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_server_by_aid_returns_none_when_not_found(self, mock_objects):
        """Test that get_server_by_aid returns None when not found"""
        mock_objects.return_value.first.return_value = None

        result = self.service.get_server_by_aid("nonexistent_aid")

        assert result is None
        mock_objects.assert_called_once_with(aid="nonexistent_aid")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_delete_server(self, mock_objects):
        """Test that delete_server deletes the server"""
        mock_query = Mock()
        mock_objects.return_value = mock_query

        self.service.delete_server("test_aid")

        mock_objects.assert_called_once_with(aid="test_aid")
        mock_query.delete.assert_called_once()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_delete_server_with_nonexistent_server(self, mock_objects):
        """Test that delete_server handles nonexistent server gracefully"""
        mock_query = Mock()
        mock_objects.return_value = mock_query

        # Should not raise an exception even if server doesn't exist
        self.service.delete_server("nonexistent_aid")

        mock_objects.assert_called_once_with(aid="nonexistent_aid")
        mock_query.delete.assert_called_once()

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_active_server_returns_most_recently_modified(self, mock_objects):
        """Test that get_active_server returns the doc with the greatest lastModified"""
        mock_server = Mock()
        mock_objects.order_by.return_value.first.return_value = mock_server

        result = ServerService.get_active_server()

        assert result == mock_server
        mock_objects.order_by.assert_called_once_with("-lastModified")

    @patch("castellan.core.services.server_service.Server.objects")
    def test_get_active_server_returns_none_when_no_servers(self, mock_objects):
        """Test that get_active_server returns None when no Server docs exist"""
        mock_objects.order_by.return_value.first.return_value = None

        result = ServerService.get_active_server()

        assert result is None


class TestServerServiceIntegration:
    """Integration tests for ServerService with realistic scenarios"""

    def setup_method(self):
        """Set up test fixtures"""
        self.mock_parser = Mock()
        self.mock_kvy = Mock()
        self.mock_kel_service = Mock()
        self.service = ServerService(
            self.mock_parser, self.mock_kvy, self.mock_kel_service
        )

    @patch("castellan.core.services.server_service.Server")
    @patch("castellan.core.services.server_service.ServerService.server_exists")
    @patch("castellan.core.services.server_service.datetime")
    @patch("castellan.core.services.server_service.asdict")
    def test_create_server_full_workflow(
        self, mock_asdict, mock_datetime, mock_server_exists, mock_server_class
    ):
        """Test complete workflow of creating a server"""
        # Setup
        mock_server_exists.return_value = False
        mock_datetime.datetime.now.return_value.timestamp.return_value = 1234567890

        mock_server = Mock()
        mock_server_class.return_value = mock_server

        mock_state = Mock()
        mock_kever = Mock()
        mock_kever.state.return_value = mock_state
        self.mock_kvy.kevers = {"server_aid_123": mock_kever}

        mock_asdict.return_value = {"i": "server_aid_123", "s": "0", "k": ["key1"]}

        # Execute
        doc = {
            "aid": "server_aid_123",
            "ipaddress": "10.0.0.1",
            "port": 5620,
        }
        kel = b'{"v":"KERI10JSON000000_","i":"server_aid_123","s":"0","t":"icp"}'

        result = self.service.create_server(doc, kel)

        # Verify
        assert result == mock_server
        assert mock_server.lastModified == 1234567890
        assert (
            mock_server.kel
            == '{"v":"KERI10JSON000000_","i":"server_aid_123","s":"0","t":"icp"}'
        )
        assert mock_server.key_state == {"i": "server_aid_123", "s": "0", "k": ["key1"]}

        # Verify parser was called correctly
        self.mock_parser.parse.assert_called_once()
        call_args = self.mock_parser.parse.call_args
        assert call_args[1]["kvy"] == self.mock_kvy
        assert call_args[1]["local"] is True

        # Verify server was saved and KEL services were called
        mock_server.save.assert_called_once()
        self.mock_kel_service.capture_kel.assert_called_once_with("server_aid_123")
        self.mock_kel_service.capture_rpys.assert_called_once_with("server_aid_123")
