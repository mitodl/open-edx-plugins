"""Tests for the sync_course_access_roles management command."""

from unittest import mock

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

COMMAND = "sync_course_access_roles"
WEBHOOK_SETTINGS = {
    "ENROLLMENT_WEBHOOK_URL": "https://example.com/api/openedx_webhook/enrollment/",
    "ENROLLMENT_WEBHOOK_ACCESS_TOKEN": "test-token",
    "ENROLLMENT_COURSE_ACCESS_ROLES": ["instructor", "staff"],
}
TASK_PATH = "ol_openedx_events_handler.tasks.notify_course_access_role_addition"


@pytest.fixture
def access_roles():
    """Patch CourseAccessRole so the command can run without real course data."""
    with mock.patch("common.djangoapps.student.models.CourseAccessRole") as mock_model:
        yield mock_model


EXPECTED_ROLE_COUNT = 2


def _role(email, role, course_id, username="someone"):
    """Build a stand-in for a CourseAccessRole row."""
    access_role = mock.MagicMock()
    access_role.role = role
    access_role.course_id = course_id
    access_role.user.email = email
    access_role.user.username = username
    return access_role


def _set_rows(access_roles, rows):
    """Wire the patched model's query chain to return ``rows``."""
    queryset = access_roles.objects.filter.return_value.select_related.return_value
    queryset.filter.return_value = queryset
    queryset.order_by.return_value.iterator.return_value = iter(rows)
    return queryset


@mock.patch(TASK_PATH)
def test_queues_a_webhook_per_role(mock_task, access_roles):
    """Each role with a course and an email is sent."""
    _set_rows(
        access_roles,
        [
            _role("staff@example.com", "staff", "course-v1:Org+Course+Run"),
            _role("admin@example.com", "instructor", "course-v1:Org+Course+Run"),
        ],
    )

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(COMMAND)

    assert mock_task.delay.call_count == EXPECTED_ROLE_COUNT
    mock_task.delay.assert_any_call(
        user_email="staff@example.com",
        course_key="course-v1:Org+Course+Run",
        role="staff",
    )


@mock.patch(TASK_PATH)
def test_dry_run_queues_nothing(mock_task, access_roles):
    """A dry run reports what it would send without sending it."""
    _set_rows(
        access_roles, [_role("staff@example.com", "staff", "course-v1:Org+Course+Run")]
    )

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(COMMAND, "--dry-run")

    mock_task.delay.assert_not_called()


@mock.patch(TASK_PATH)
def test_skips_org_wide_roles(mock_task, access_roles):
    """
    An org-wide role has no course_id, so there is no run to attach it to.

    Open edX stores one as a CourseAccessRole with an empty course_id; the
    consumer keys its records on a single course run, so sending it would be
    meaningless.
    """
    _set_rows(access_roles, [_role("staff@example.com", "staff", "")])

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(COMMAND)

    mock_task.delay.assert_not_called()


@mock.patch(TASK_PATH)
def test_skips_users_without_an_email(mock_task, access_roles):
    """The consumer identifies users by email, so a user without one is skipped."""
    _set_rows(
        access_roles, [_role("", "staff", "course-v1:Org+Course+Run", "no-email")]
    )

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(COMMAND)

    mock_task.delay.assert_not_called()


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"ENROLLMENT_WEBHOOK_URL": None}, id="no-webhook-url"),
        pytest.param({"ENROLLMENT_WEBHOOK_ACCESS_TOKEN": None}, id="no-access-token"),
        pytest.param({"ENROLLMENT_COURSE_ACCESS_ROLES": []}, id="no-allowed-roles"),
    ],
)
@mock.patch(TASK_PATH)
def test_refuses_when_misconfigured(mock_task, access_roles, overrides):  # noqa: ARG001
    """
    Bail out rather than queue a batch of webhooks that cannot land.

    A backfill is a bulk operation, so failing loudly up front beats queueing
    thousands of tasks that each fail on their own. It raises rather than
    returning so the process exits non-zero, which is the only thing an
    automated run can act on.
    """
    with (
        override_settings(**{**WEBHOOK_SETTINGS, **overrides}),
        pytest.raises(CommandError),
    ):
        call_command(COMMAND)

    mock_task.delay.assert_not_called()


@mock.patch(TASK_PATH)
def test_course_id_narrows_the_queryset(mock_task, access_roles):  # noqa: ARG001
    """--course-id is repeatable and filters the roles that get sent."""
    queryset = _set_rows(
        access_roles, [_role("staff@example.com", "staff", "course-v1:Org+Course+Run")]
    )

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(
            COMMAND,
            "--course-id",
            "course-v1:Org+Course+Run",
            "--course-id",
            "course-v1:Org+Other+Run",
        )

    queryset.filter.assert_called_once_with(
        course_id__in=["course-v1:Org+Course+Run", "course-v1:Org+Other+Run"]
    )


@mock.patch(TASK_PATH)
def test_without_course_id_no_extra_filter(mock_task, access_roles):  # noqa: ARG001
    """Omitting --course-id leaves the role queryset unnarrowed."""
    queryset = _set_rows(
        access_roles, [_role("staff@example.com", "staff", "course-v1:Org+Course+Run")]
    )

    with override_settings(**WEBHOOK_SETTINGS):
        call_command(COMMAND)

    queryset.filter.assert_not_called()
