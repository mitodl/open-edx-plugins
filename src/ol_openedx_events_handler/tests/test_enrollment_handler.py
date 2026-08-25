"""Tests for the COURSE_ENROLLMENT_CREATED event handler."""

from unittest import mock

import pytest
from django.test import override_settings
from ol_openedx_events_handler.handlers.enrollment import (
    handle_course_enrollment_created,
)

VALID_WEBHOOK_PATCH = mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=True,
)
TASK_PATCH = mock.patch(
    "ol_openedx_events_handler.tasks.notify_course_enrollment_created"
)
# The handler defers dispatch to transaction.on_commit. Outside a transaction
# Django needs a database connection to decide that, so run the callback inline.
ON_COMMIT_PATCH = mock.patch(
    "ol_openedx_events_handler.handlers.enrollment.transaction.on_commit",
    side_effect=lambda func: func(),
)

COURSE_KEY = "course-v1:MITx+1.001x+2025_T1"
LEARNER_EMAIL = "learner@example.com"
SERVICE_WORKER = "mitxonline_service_worker"


def _make_enrollment_data(*, email=LEARNER_EMAIL, mode="audit"):
    """Build a mock CourseEnrollmentData object."""
    user_pii = mock.MagicMock()
    user_pii.email = email
    user_pii.username = "learner"

    user = mock.MagicMock()
    user.pii = user_pii

    course = mock.MagicMock()
    course.course_key = COURSE_KEY

    enrollment = mock.MagicMock()
    enrollment.user = user
    enrollment.course = course
    enrollment.mode = mode
    enrollment.is_active = True
    return enrollment


def _make_user(username):
    """Build a mock acting user."""
    user = mock.MagicMock()
    user.username = username
    return user


@pytest.mark.parametrize("mode", ["audit", "verified"])
@ON_COMMIT_PATCH
@VALID_WEBHOOK_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
def test_dispatches_for_manual_enrollment(
    mock_get_current_user,
    mock_task,
    _mock_validate,  # noqa: PT019
    _mock_on_commit,  # noqa: PT019
    mode,
):
    """An enrollment made by a staff member should be sent to the webhook."""
    mock_get_current_user.return_value = _make_user("course_team_member")

    with override_settings(
        ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME=SERVICE_WORKER,
    ):
        handle_course_enrollment_created(
            sender=None,
            enrollment=_make_enrollment_data(mode=mode),
        )

    mock_task.delay.assert_called_once_with(
        user_email=LEARNER_EMAIL,
        course_key=COURSE_KEY,
        mode=mode,
    )


@pytest.mark.parametrize(
    ("acting_username", "service_worker_setting", "expect_dispatch"),
    [
        pytest.param(
            SERVICE_WORKER,
            SERVICE_WORKER,
            False,
            id="skips-webhook-consumer-own-enrollment",
        ),
        pytest.param(
            "course_team_member",
            SERVICE_WORKER,
            True,
            id="dispatches-for-other-users",
        ),
        pytest.param(
            SERVICE_WORKER,
            None,
            True,
            id="dispatches-when-service-worker-not-configured",
        ),
        pytest.param(
            None,
            SERVICE_WORKER,
            True,
            id="dispatches-when-acting-user-is-unknown",
        ),
        pytest.param(
            "",
            SERVICE_WORKER,
            True,
            id="dispatches-for-anonymous-user",
        ),
    ],
)
@ON_COMMIT_PATCH
@VALID_WEBHOOK_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
def test_service_worker_filtering(
    mock_get_current_user,
    mock_task,
    _mock_validate,  # noqa: PT019
    _mock_on_commit,  # noqa: PT019
    acting_username,
    service_worker_setting,
    expect_dispatch,
):
    """Only the webhook consumer's own enrollments are filtered out."""
    mock_get_current_user.return_value = (
        None if acting_username is None else _make_user(acting_username)
    )

    with override_settings(
        ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME=service_worker_setting,
    ):
        handle_course_enrollment_created(
            sender=None,
            enrollment=_make_enrollment_data(),
        )

    if expect_dispatch:
        mock_task.delay.assert_called_once_with(
            user_email=LEARNER_EMAIL,
            course_key=COURSE_KEY,
            mode="audit",
        )
    else:
        mock_task.delay.assert_not_called()


@ON_COMMIT_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
@mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=False,
)
def test_skips_when_webhook_not_configured(
    _mock_validate,  # noqa: PT019
    mock_get_current_user,
    mock_task,
    _mock_on_commit,  # noqa: PT019
):
    """No task should be queued when the webhook settings are missing."""
    mock_get_current_user.return_value = _make_user("course_team_member")

    handle_course_enrollment_created(
        sender=None,
        enrollment=_make_enrollment_data(),
    )

    mock_task.delay.assert_not_called()


@ON_COMMIT_PATCH
@VALID_WEBHOOK_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
def test_skips_when_email_is_missing(
    mock_get_current_user,
    mock_task,
    _mock_validate,  # noqa: PT019
    _mock_on_commit,  # noqa: PT019
):
    """The webhook identifies the learner by email, so it is required."""
    mock_get_current_user.return_value = _make_user("course_team_member")

    handle_course_enrollment_created(
        sender=None,
        enrollment=_make_enrollment_data(email=""),
    )

    mock_task.delay.assert_not_called()


@VALID_WEBHOOK_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.transaction.on_commit")
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
def test_dispatch_is_deferred_until_commit(
    mock_get_current_user,
    mock_on_commit,
    mock_task,
    _mock_validate,  # noqa: PT019
):
    """The task must not be queued before the enrollment transaction commits."""
    mock_get_current_user.return_value = _make_user("course_team_member")

    handle_course_enrollment_created(
        sender=None,
        enrollment=_make_enrollment_data(),
    )

    mock_task.delay.assert_not_called()
    mock_on_commit.assert_called_once()


@ON_COMMIT_PATCH
@VALID_WEBHOOK_PATCH
@TASK_PATCH
@mock.patch("ol_openedx_events_handler.handlers.enrollment.get_current_user")
def test_queueing_failure_does_not_propagate(
    mock_get_current_user,
    mock_task,
    _mock_validate,  # noqa: PT019
    _mock_on_commit,  # noqa: PT019
):
    """A broker outage must not surface as an enrollment failure."""
    mock_get_current_user.return_value = _make_user("course_team_member")
    mock_task.delay.side_effect = OSError("broker unreachable")

    handle_course_enrollment_created(
        sender=None,
        enrollment=_make_enrollment_data(),
    )

    mock_task.delay.assert_called_once()
