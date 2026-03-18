"""Tests for the course staff webhook Celery task."""

from unittest import mock

import pytest
import requests
from django.test import override_settings
from ol_openedx_events_handler.tasks.course_access_role import (
    notify_course_access_role_addition,
)

WEBHOOK_URL = "https://example.com/api/v1/staff_enrollment_webhook/"
WEBHOOK_KEY = "test-api-key-123"
USER_EMAIL = "instructor@example.com"
COURSE_KEY = "course-v1:MITx+1.001x+2025_T1"
ROLE = "instructor"


@pytest.mark.parametrize(
    ("webhook_key", "expect_auth"),
    [
        pytest.param(WEBHOOK_KEY, True, id="with-auth-key"),
        pytest.param(None, False, id="without-auth-key"),
    ],
)
@mock.patch("ol_openedx_events_handler.tasks.course_access_role.requests.post")
def test_sends_webhook_with_correct_payload(mock_post, webhook_key, expect_auth):
    """POST correct payload and conditionally include auth header."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    with override_settings(
        ENROLLMENT_WEBHOOK_URL=WEBHOOK_URL,
        ENROLLMENT_WEBHOOK_KEY=webhook_key,
    ):
        notify_course_access_role_addition(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
            role=ROLE,
        )

    expected_headers = {"Content-Type": "application/json"}
    if expect_auth:
        expected_headers["Authorization"] = f"Bearer {webhook_key}"

    mock_post.assert_called_once_with(
        WEBHOOK_URL,
        json={
            "email": USER_EMAIL,
            "course_id": COURSE_KEY,
            "role": ROLE,
        },
        headers=expected_headers,
        timeout=30,
    )
    mock_response.raise_for_status.assert_called_once()


@override_settings(
    ENROLLMENT_WEBHOOK_URL=WEBHOOK_URL,
    ENROLLMENT_WEBHOOK_KEY=WEBHOOK_KEY,
)
@mock.patch("ol_openedx_events_handler.tasks.course_access_role.requests.post")
def test_raises_on_http_error(mock_post):
    """HTTP errors should propagate for Celery retry."""
    mock_response = mock.MagicMock()
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        "500 Server Error"
    )
    mock_post.return_value = mock_response

    with pytest.raises(requests.exceptions.HTTPError):
        notify_course_access_role_addition(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
            role=ROLE,
        )
