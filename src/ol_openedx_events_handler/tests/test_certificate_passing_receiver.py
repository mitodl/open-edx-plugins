"""Tests for the COURSE_GRADE_NOW_PASSED signal handler."""

from unittest import mock

from ol_openedx_events_handler.receivers.certificate_passing_receiver import (
    listen_for_passing_grade,
)

COURSE_KEY = "course-v1:MITx+6.001x+2026_T1"
VALID_WEBHOOK_PATCH = mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    ".validate_certificate_webhook",
    return_value=True,
)
TASK_PATCH = mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    ".create_certificate_for_passing_grade"
)


@mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    "._is_eligible_for_certificate",
    return_value=False,
)
@TASK_PATCH
def test_skips_when_not_eligible(mock_task, _mock_is_eligible):  # noqa: PT019
    """Do nothing when the enrollment is not certificate-eligible."""
    user = mock.MagicMock(email="user@example.com", username="user")

    listen_for_passing_grade(sender=None, user=user, course_id=COURSE_KEY)

    mock_task.delay.assert_not_called()


@VALID_WEBHOOK_PATCH
@mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    "._is_eligible_for_certificate",
    return_value=True,
)
@TASK_PATCH
def test_dispatches_certificate_task(
    mock_task,
    _mock_is_eligible,  # noqa: PT019
    _mock_validate,  # noqa: PT019
):
    """Dispatch certificate task when learner is eligible and configured."""
    user = mock.MagicMock(email="user@example.com", username="user")

    listen_for_passing_grade(sender=None, user=user, course_id=COURSE_KEY)

    mock_task.delay.assert_called_once_with(
        user_email="user@example.com",
        course_key=COURSE_KEY,
    )


@mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    ".validate_certificate_webhook",
    return_value=False,
)
@mock.patch(
    "ol_openedx_events_handler.receivers.certificate_passing_receiver"
    "._is_eligible_for_certificate",
    return_value=True,
)
@TASK_PATCH
def test_skips_when_certificate_webhook_not_configured(
    mock_task,
    _mock_is_eligible,  # noqa: PT019
    _mock_validate,  # noqa: PT019
):
    """Skip dispatch when no certificate webhook URL is configured."""
    user = mock.MagicMock(email="user@example.com", username="user")

    listen_for_passing_grade(sender=None, user=user, course_id=COURSE_KEY)

    mock_task.delay.assert_not_called()
