"""Tests for the sync_course_access_roles management command."""

import io
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
COURSE = "course-v1:Org+Course+Run"
OTHER_COURSE = "course-v1:Org+Other+Run"


def _make_role(email, role, course_id, username=None):
    """Create a real CourseAccessRole row, so the command's filters are exercised."""
    from common.djangoapps.student.models import CourseAccessRole  # noqa: PLC0415
    from django.contrib.auth import get_user_model  # noqa: PLC0415
    from opaque_keys.edx.keys import CourseKey  # noqa: PLC0415

    user = get_user_model().objects.create(
        username=username or f"{role}-{email or 'noemail'}-{course_id or 'org'}",
        email=email,
    )
    return CourseAccessRole.objects.create(
        user=user,
        role=role,
        course_id=CourseKey.from_string(course_id) if course_id else None,
        org=CourseKey.from_string(course_id).org if course_id else "Org",
    )


def _run(*args):
    """Run the command, returning its stdout."""
    out = io.StringIO()
    call_command(COMMAND, *args, stdout=out, stderr=io.StringIO())
    return out.getvalue()


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_queues_a_webhook_per_allowed_role(mock_task):
    """Each role in ENROLLMENT_COURSE_ACCESS_ROLES with a course and email is sent."""
    _make_role("staff@example.com", "staff", COURSE)
    _make_role("admin@example.com", "instructor", COURSE)

    with override_settings(**WEBHOOK_SETTINGS):
        output = _run()

    assert mock_task.delay.call_count == 2  # noqa: PLR2004
    mock_task.delay.assert_any_call(
        user_email="staff@example.com", course_key=COURSE, role="staff"
    )
    assert "staff@example.com — staff in " + COURSE in output
    assert "Queued 2 role(s)" in output


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_roles_outside_the_setting_are_not_sent(mock_task):
    """
    A role the consumer was never told about is skipped by the queryset filter.

    Real rows rather than a mocked queryset, so `role__in=allowed_roles` is
    actually exercised - with a mock that returns the same rows regardless of
    filter, dropping that filter would leave every test green.
    """
    _make_role("researcher@example.com", "data_researcher", COURSE)
    _make_role("beta@example.com", "beta_testers", COURSE)
    _make_role("staff@example.com", "staff", COURSE)

    with override_settings(**WEBHOOK_SETTINGS):
        _run()

    mock_task.delay.assert_called_once_with(
        user_email="staff@example.com", course_key=COURSE, role="staff"
    )


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_a_widened_setting_sends_the_extra_role(mock_task):
    """Adding a role to the setting is all it takes for it to be sent."""
    _make_role("researcher@example.com", "data_researcher", COURSE)

    with override_settings(
        **{
            **WEBHOOK_SETTINGS,
            "ENROLLMENT_COURSE_ACCESS_ROLES": [
                "instructor",
                "staff",
                "data_researcher",
            ],
        }
    ):
        _run()

    mock_task.delay.assert_called_once_with(
        user_email="researcher@example.com", course_key=COURSE, role="data_researcher"
    )


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_dry_run_lists_without_queueing(mock_task):
    """A dry run reports what it would send, and queues nothing."""
    _make_role("staff@example.com", "staff", COURSE)

    with override_settings(**WEBHOOK_SETTINGS):
        output = _run("--dry-run")

    mock_task.delay.assert_not_called()
    assert "staff@example.com — staff in " + COURSE in output
    assert "Would send 1 role(s)" in output


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_course_id_narrows_to_the_named_courses(mock_task):
    """--course-id is repeatable and limits which roles are sent."""
    _make_role("a@example.com", "staff", COURSE)
    _make_role("b@example.com", "staff", OTHER_COURSE)
    _make_role("c@example.com", "staff", "course-v1:Org+Third+Run")

    with override_settings(**WEBHOOK_SETTINGS):
        _run("--course-id", COURSE, "--course-id", OTHER_COURSE)

    sent = sorted(c.kwargs["user_email"] for c in mock_task.delay.call_args_list)
    assert sent == ["a@example.com", "b@example.com"]


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_skips_are_reported_by_reason(mock_task):
    """
    Org-wide and missing-email skips are counted separately.

    One mixed run rather than a row per test: with a single row, a `continue`
    that should be a `break` would pass just as well.
    """
    _make_role("", "staff", COURSE, username="no-email-user")
    _make_role("orgwide@example.com", "staff", None)
    _make_role("valid@example.com", "staff", COURSE)

    with override_settings(**WEBHOOK_SETTINGS):
        output = _run()

    mock_task.delay.assert_called_once_with(
        user_email="valid@example.com", course_key=COURSE, role="staff"
    )
    assert "Queued 1 role(s); skipped 1 org-wide and 1 with no email." in output


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"ENROLLMENT_WEBHOOK_URL": None}, id="no-webhook-url"),
        pytest.param({"ENROLLMENT_WEBHOOK_ACCESS_TOKEN": None}, id="no-access-token"),
        pytest.param({"ENROLLMENT_COURSE_ACCESS_ROLES": []}, id="no-allowed-roles"),
    ],
)
@mock.patch(TASK_PATH)
def test_refuses_when_misconfigured(mock_task, overrides):
    """
    Bail out rather than queue a batch of webhooks that cannot land.

    It raises rather than returning so the process exits non-zero, which is the
    only thing an automated run can act on.
    """
    with (
        override_settings(**{**WEBHOOK_SETTINGS, **overrides}),
        pytest.raises(CommandError),
    ):
        _run()

    mock_task.delay.assert_not_called()


# transaction=True because the point of this test is a real connection close.
# Under the default django_db the test body runs inside an atomic block, so
# closing the connection poisons that transaction instead of reproducing what
# happens in production, where no such block is held.
@pytest.mark.django_db(transaction=True)
@mock.patch(TASK_PATH)
def test_survives_the_connection_closing_between_dispatches(mock_task):
    """
    A task that closes the database connection does not abort the backfill.

    Celery closes Django's connection when a task finishes, so on a deployment
    that runs tasks eagerly that happens inside this loop. Holding a cursor
    across the dispatch - what .iterator() does - makes the next read fail with
    "MySQL server has gone away", ending the backfill partway while the command
    has already claimed it queued everything.
    """
    from django.db import connection  # noqa: PLC0415

    total = 5
    for n in range(total):
        _make_role(f"staff{n}@example.com", "staff", COURSE, username=f"closer-{n}")

    # On an install where the plugin's receiver is active, creating the rows
    # above already called this mock. Only the command's dispatches matter here.
    mock_task.reset_mock()
    mock_task.delay.side_effect = lambda **_kwargs: connection.close()

    with override_settings(**WEBHOOK_SETTINGS):
        output = _run()

    assert mock_task.delay.call_count == total
    assert f"Queued {total} role(s)" in output


@pytest.mark.django_db
@mock.patch(TASK_PATH)
def test_pages_through_roles_beyond_one_batch(mock_task):
    """Every role is sent when there are more of them than fit in one page."""
    from ol_openedx_events_handler.management.commands import (  # noqa: PLC0415
        sync_course_access_roles as cmd,
    )

    total = 7
    for n in range(total):
        _make_role(f"paged{n}@example.com", "staff", COURSE, username=f"paged-{n}")

    mock_task.reset_mock()

    with mock.patch.object(cmd, "BATCH_SIZE", 2), override_settings(**WEBHOOK_SETTINGS):
        output = _run()

    assert mock_task.delay.call_count == total
    assert f"Queued {total} role(s)" in output
    emailed = sorted(c.kwargs["user_email"] for c in mock_task.delay.call_args_list)
    assert emailed == sorted(f"paged{n}@example.com" for n in range(total))
