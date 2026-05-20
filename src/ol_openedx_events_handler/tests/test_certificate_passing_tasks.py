"""Tests for the certificate passing webhook Celery task."""

from unittest import mock

import pytest
import requests
from django.test import override_settings
from ol_openedx_events_handler.tasks import (
    create_certificate_for_passing_grade,
)

WEBHOOK_URL = "https://example.com/api/openedx_webhook/certificate/"
ACCESS_TOKEN = "certificate-access-token"  # noqa: S105
USER_EMAIL = "learner@example.com"
COURSE_KEY = "course-v1:MITx+6.001x+2026_T1"


@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_sends_certificate_webhook(mock_post):
    """POST the certificate payload with the configured auth header."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    with override_settings(
        CERTIFICATE_WEBHOOK_URL=WEBHOOK_URL,
        CERTIFICATE_WEBHOOK_ACCESS_TOKEN=ACCESS_TOKEN,
    ):
        create_certificate_for_passing_grade(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
        )

    mock_post.assert_called_once_with(
        WEBHOOK_URL,
        json={
            "email": USER_EMAIL,
            "course_id": COURSE_KEY,
        },
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {ACCESS_TOKEN}",
        },
        timeout=30,
    )
    mock_response.raise_for_status.assert_called_once()


@override_settings(
    CERTIFICATE_WEBHOOK_URL=WEBHOOK_URL,
    CERTIFICATE_WEBHOOK_ACCESS_TOKEN=ACCESS_TOKEN,
)
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_raises_on_http_error(mock_post):
    """HTTP errors should propagate for Celery retry."""
    mock_response = mock.MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    mock_post.return_value = mock_response

    with pytest.raises(requests.exceptions.HTTPError):
        create_certificate_for_passing_grade(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
        )


@pytest.mark.parametrize(
    ("certificate_webhook_url", "certificate_webhook_access_token"),
    [
        pytest.param(None, ACCESS_TOKEN, id="missing-webhook-url"),
        pytest.param(WEBHOOK_URL, None, id="missing-access-token"),
    ],
)
@mock.patch("ol_openedx_events_handler.tasks.log.error")
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_skips_dispatch_when_webhook_not_fully_configured(
    mock_post,
    mock_log_error,
    certificate_webhook_url,
    certificate_webhook_access_token,
):
    """Do not call certificate webhook when required settings are missing."""
    with override_settings(
        CERTIFICATE_WEBHOOK_URL=certificate_webhook_url,
        CERTIFICATE_WEBHOOK_ACCESS_TOKEN=certificate_webhook_access_token,
    ):
        create_certificate_for_passing_grade(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
        )

    mock_post.assert_not_called()
    mock_log_error.assert_called_once()
