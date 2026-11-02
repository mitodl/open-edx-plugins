"""Shared test fixtures for ol_openedx_chat tests."""

import pytest
from django.test import RequestFactory


@pytest.fixture
def request_factory():
    """Provide a Django RequestFactory."""
    return RequestFactory()
