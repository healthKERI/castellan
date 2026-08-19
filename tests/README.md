# Castellan Tests

This directory contains the test suite for the Castellan credential management server.

## Setup

Install the package with test dependencies:

```bash
pip install -e ".[test]"
```

This will install pytest, pytest-cov, pytest-mock, and pytest-asyncio.

## Running Tests

Run all tests:
```bash
pytest
```

Run specific test file:
```bash
pytest tests/castellan/test_account_service.py
```

Run specific test class:
```bash
pytest tests/castellan/test_account_service.py::TestAccountService
```

Run specific test:
```bash
pytest tests/castellan/test_account_service.py::TestAccountService::test_create_account_success
```

Run with coverage report:
```bash
pytest --cov=castellan --cov-report=html
```

Run only unit tests:
```bash
pytest -m unit
```

Run only integration tests:
```bash
pytest -m integration
```

## Test Structure

- `test_account_service.py` - Comprehensive tests for the AccountService class
  - `TestAccount` - Tests for Account model static methods
  - `TestAccountService` - Tests for AccountService instance methods
  - `TestAccountServiceIntegration` - Integration tests for realistic workflows
