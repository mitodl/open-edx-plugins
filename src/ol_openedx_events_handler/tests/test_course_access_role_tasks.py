"""Tests for the course access role webhook Celery task."""

from unittest import mock

import pytest
import requests
from django.test import override_settings
from ol_openedx_events_handler.tasks.course_access_role import (
    notify_course_access_role_addition,
)

WEBHOOK_URL = "https://example.com/api/openedx_webhook/enrollment/"
TEST_TOKEN = "test-access-token-123"  # noqa: S105
USER_EMAIL = "instructor@example.com"
COURSE_KEY = "course-v1:MITx+1.001x+2025_T1"
ROLE = "instructor"


@pytest.mark.parametrize(
    ("access_token", "expect_auth"),
    [
        pytest.param(TEST_TOKEN, True, id="with-access-token"),
        pytest.param(None, False, id="without-access-token"),
    ],
)
@mock.patch("ol_openedx_events_handler.tasks.course_access_role.requests.post")
def test_sends_webhook_with_correct_payload(mock_post, access_token, expect_auth):
    """POST correct payload and conditionally include auth header."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 200
    mock_post.return_value = mock_response

    with override_settings(
        ENROLLMENT_WEBHOOK_URL=WEBHOOK_URL,
        ENROLLMENT_WEBHOOK_ACCESS_TOKEN=access_token,
    ):
        notify_course_access_role_addition(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
            role=ROLE,
        )

    expected_headers = {"Content-Type": "application/json"}
    if expect_auth:
        expected_headers["Authorization"] = f"Bearer {access_token}"

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
    ENROLLMENT_WEBHOOK_ACCESS_TOKEN=TEST_TOKEN,
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
