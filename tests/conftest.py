# -*- encoding: utf-8 -*-
"""
Pytest configuration and shared fixtures for Castellan tests.
"""

import pytest
from unittest.mock import Mock


@pytest.fixture
def mock_parser():
    """Fixture providing a mock parser for KERI event parsing"""
    parser = Mock()
    parser.parse = Mock()
    return parser


@pytest.fixture
def mock_kvy():
    """Fixture providing a mock Kevery instance"""
    kvy = Mock()
    kvy.kevers = {}
    return kvy


@pytest.fixture
def mock_kever():
    """Fixture providing a mock Kever instance"""
    kever = Mock()
    serder = Mock()
    serder.sn = 0
    kever.serder = serder

    state = Mock()
    state.dict = Mock(return_value={"i": "test_aid", "s": "0"})
    kever.state = Mock(return_value=state)

    return kever


@pytest.fixture
def sample_account_doc():
    """Fixture providing sample account document data"""
    return {
        "aid": "test_aid_123",
        "username": "testuser",
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def sample_kel():
    """Fixture providing sample KEL (Key Event Log) data"""
    return b'{"v":"KERI10JSON000000_","i":"test_aid_123","s":"0","t":"icp"}'
