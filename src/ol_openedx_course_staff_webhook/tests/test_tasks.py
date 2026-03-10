"""Tests for the course staff webhook Celery task."""

from unittest import mock

import pytest
import requests
from django.test import TestCase, override_settings
from ol_openedx_course_staff_webhook.tasks import (
    notify_course_staff_addition,
)

WEBHOOK_URL = (
    "https://mitxonline.example.com"
    "/api/v1/staff_enrollment_webhook/"
)
WEBHOOK_KEY = "test-api-key-123"


class TestNotifyCourseStaffTask(TestCase):
    """Tests for notify_course_staff_addition task."""

    @override_settings(
        MITXONLINE_WEBHOOK_URL=WEBHOOK_URL,
        MITXONLINE_WEBHOOK_KEY=WEBHOOK_KEY,
    )
    @mock.patch(
        "ol_openedx_course_staff_webhook.tasks.requests.post"
    )
    def test_sends_webhook_with_correct_payload(self, mock_post):
        """POST correct payload to the configured webhook URL."""
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        notify_course_staff_addition(
            user_email="instructor@example.com",
            course_key="course-v1:MITx+1.001x+2025_T1",
            role="instructor",
        )

        mock_post.assert_called_once_with(
            WEBHOOK_URL,
            json={
                "email": "instructor@example.com",
                "course_id": "course-v1:MITx+1.001x+2025_T1",
                "role": "instructor",
            },
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {WEBHOOK_KEY}",
            },
            timeout=30,
        )
        mock_response.raise_for_status.assert_called_once()

    @override_settings(
        MITXONLINE_WEBHOOK_URL=WEBHOOK_URL,
        MITXONLINE_WEBHOOK_KEY=None,
    )
    @mock.patch(
        "ol_openedx_course_staff_webhook.tasks.requests.post"
    )
    def test_sends_webhook_without_auth_when_key_is_none(
        self, mock_post
    ):
        """Task should omit Auth header when key is None."""
        mock_response = mock.MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        notify_course_staff_addition(
            user_email="staff@example.com",
            course_key="course-v1:MITx+2.002x+2025_T1",
            role="staff",
        )

        call_kwargs = mock_post.call_args[1]
        assert "Authorization" not in call_kwargs["headers"]

    @override_settings(MITXONLINE_WEBHOOK_URL=None)
    @mock.patch(
        "ol_openedx_course_staff_webhook.tasks.requests.post"
    )
    @mock.patch(
        "ol_openedx_course_staff_webhook.tasks.log"
    )
    def test_skips_webhook_when_url_not_configured(
        self, mock_log, mock_post
    ):
        """Log warning and skip when URL is not set."""
        notify_course_staff_addition(
            user_email="instructor@example.com",
            course_key="course-v1:MITx+1.001x+2025_T1",
            role="instructor",
        )

        mock_post.assert_not_called()
        mock_log.warning.assert_called_once()

    @override_settings(
        MITXONLINE_WEBHOOK_URL=WEBHOOK_URL,
        MITXONLINE_WEBHOOK_KEY=WEBHOOK_KEY,
    )
    @mock.patch(
        "ol_openedx_course_staff_webhook.tasks.requests.post"
    )
    def test_raises_on_http_error(self, mock_post):
        """HTTP errors should propagate for Celery retry."""
        mock_response = mock.MagicMock()
        mock_response.raise_for_status.side_effect = (
            requests.exceptions.HTTPError("500 Server Error")
        )
        mock_post.return_value = mock_response

        with pytest.raises(requests.exceptions.HTTPError):
            notify_course_staff_addition(
                user_email="instructor@example.com",
                course_key="course-v1:MITx+1.001x+2025_T1",
                role="instructor",
            )
