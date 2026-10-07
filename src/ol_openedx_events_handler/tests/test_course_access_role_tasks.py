"""Tests for the course access role webhook Celery task."""

from unittest import mock

import pytest
import requests
from django.test import override_settings
from ol_openedx_events_handler.tasks import (
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
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
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
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_raises_on_http_error(mock_post):
    """HTTP errors should propagate for Celery retry."""
    mock_response = mock.MagicMock()
    mock_response.status_code = 500
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


@pytest.mark.parametrize(
    "status_code",
    [400, 401, 403, 404, 422],
)
@override_settings(
    ENROLLMENT_WEBHOOK_URL=WEBHOOK_URL,
    ENROLLMENT_WEBHOOK_ACCESS_TOKEN=TEST_TOKEN,
)
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_does_not_retry_on_client_error(mock_post, status_code):
    """
    A 4xx is logged and dropped rather than retried.

    Resending it unchanged can never succeed, and the two retries are better
    spent on a webhook that might still land.
    """
    mock_response = mock.MagicMock()
    mock_response.status_code = status_code
    mock_post.return_value = mock_response

    notify_course_access_role_addition(
        user_email=USER_EMAIL,
        course_key=COURSE_KEY,
        role=ROLE,
    )

    mock_response.raise_for_status.assert_not_called()


@pytest.mark.parametrize(
    "status_code",
    [408, 429, 500, 502, 503],
)
@override_settings(
    ENROLLMENT_WEBHOOK_URL=WEBHOOK_URL,
    ENROLLMENT_WEBHOOK_ACCESS_TOKEN=TEST_TOKEN,
)
@mock.patch("ol_openedx_events_handler.tasks.requests.post")
def test_retries_on_transient_error(mock_post, status_code):
    """A transient client error or any 5xx still raises, so Celery retries."""
    mock_response = mock.MagicMock()
    mock_response.status_code = status_code
    mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
        f"{status_code} Error"
    )
    mock_post.return_value = mock_response

    with pytest.raises(requests.exceptions.HTTPError):
        notify_course_access_role_addition(
            user_email=USER_EMAIL,
            course_key=COURSE_KEY,
            role=ROLE,
        )
