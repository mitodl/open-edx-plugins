"""Tests for the enrollment webhook validation utility."""

import pytest
from django.test import override_settings
from ol_openedx_events_handler.utils import validate_enrollment_webhook

WEBHOOK_URL = "https://example.com/api/openedx_webhook/enrollment/"
WEBHOOK_KEY = "test-api-key-123"


@pytest.mark.parametrize(
    ("webhook_url", "webhook_key", "expected"),
    [
        pytest.param(WEBHOOK_URL, WEBHOOK_KEY, True, id="fully-configured"),
        pytest.param(None, WEBHOOK_KEY, False, id="url-missing"),
        pytest.param(WEBHOOK_URL, None, False, id="key-missing"),
        pytest.param(None, None, False, id="both-missing"),
    ],
)
def test_validate_enrollment_webhook(webhook_url, webhook_key, expected):
    """Should return True only when both URL and key are configured."""
    with override_settings(
        ENROLLMENT_WEBHOOK_URL=webhook_url,
        ENROLLMENT_WEBHOOK_KEY=webhook_key,
    ):
        assert validate_enrollment_webhook() is expected
