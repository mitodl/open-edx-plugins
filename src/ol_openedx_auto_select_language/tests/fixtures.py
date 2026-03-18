"""Shared test fixtures for ol_openedx_auto_select_language tests."""

import pytest
from django.test import RequestFactory


@pytest.fixture
def request_factory():
    """Provide a Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
def mock_user(mocker):
    """Provide a mock authenticated user."""
    return mocker.Mock(is_authenticated=True)
