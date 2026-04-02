"""Tests for the enrollment webhook validation utility."""

import pytest
from django.test import override_settings
from ol_openedx_events_handler.utils import validate_enrollment_webhook

WEBHOOK_URL = "https://example.com/api/openedx_webhook/enrollment/"
TEST_TOKEN = "test-access-token-123"  # noqa: S105


@pytest.mark.parametrize(
    ("webhook_url", "access_token", "expected"),
    [
        pytest.param(WEBHOOK_URL, TEST_TOKEN, True, id="fully-configured"),
        pytest.param(None, TEST_TOKEN, False, id="url-missing"),
        pytest.param(WEBHOOK_URL, None, False, id="token-missing"),
        pytest.param(None, None, False, id="both-missing"),
    ],
)
def test_validate_enrollment_webhook(webhook_url, access_token, expected):
    """Should return True only when both URL and token are configured."""
    with override_settings(
        ENROLLMENT_WEBHOOK_URL=webhook_url,
        ENROLLMENT_WEBHOOK_ACCESS_TOKEN=access_token,
    ):
        assert validate_enrollment_webhook() is expected
