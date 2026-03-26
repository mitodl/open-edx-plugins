"""Tests for the COURSE_ACCESS_ROLE_ADDED signal handler."""

from unittest import mock

import pytest
from django.test import override_settings
from ol_openedx_events_handler.handlers.course_access_role import (
    handle_course_access_role_added,
)

VALID_WEBHOOK_PATCH = mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=True,
)
TASK_PATCH = mock.patch(
    "ol_openedx_events_handler.tasks.course_access_role"
    ".notify_course_access_role_addition"
)
COURSE_KEY = "course-v1:MITx+1.001x+2025_T1"
DEFAULT_ROLES = ["instructor", "staff"]


def _make_role_data(
    *,
    email="staff@example.com",
    username="staff",
    course_key=COURSE_KEY,
    role="instructor",
):
    """Build a mock CourseAccessRoleData object."""
    user_pii = mock.MagicMock()
    user_pii.email = email
    user_pii.username = username

    user = mock.MagicMock()
    user.pii = user_pii

    role_data = mock.MagicMock()
    role_data.user = user
    role_data.course_key = course_key
    role_data.org_key = "MITx"
    role_data.role = role
    return role_data


@pytest.mark.parametrize(
    ("email", "role", "allowed_roles", "expect_dispatch"),
    [
        pytest.param(
            "instructor@example.com",
            "instructor",
            DEFAULT_ROLES,
            True,
            id="dispatches-for-instructor",
        ),
        pytest.param(
            "staff@example.com",
            "staff",
            DEFAULT_ROLES,
            True,
            id="dispatches-for-staff",
        ),
        pytest.param(
            "staff@example.com",
            "data_researcher",
            ["instructor", "staff", "data_researcher"],
            True,
            id="dispatches-for-custom-role",
        ),
        pytest.param(
            "staff@example.com",
            "beta_testers",
            DEFAULT_ROLES,
            False,
            id="ignores-non-staff-role",
        ),
        pytest.param(
            "staff@example.com",
            "staff",
            ["instructor"],
            False,
            id="ignores-excluded-by-custom-roles",
        ),
    ],
)
@VALID_WEBHOOK_PATCH
@TASK_PATCH
def test_role_based_dispatch(
    mock_task,
    _mock_validate,  # noqa: PT019
    email,
    role,
    allowed_roles,
    expect_dispatch,
):
    """Task should only be triggered for roles in the allowed list."""
    role_data = _make_role_data(email=email, role=role)

    with override_settings(ENROLLMENT_COURSE_ACCESS_ROLES=allowed_roles):
        handle_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

    if expect_dispatch:
        mock_task.delay.assert_called_once_with(
            user_email=email,
            course_key=COURSE_KEY,
            role=role,
        )
    else:
        mock_task.delay.assert_not_called()


@VALID_WEBHOOK_PATCH
@mock.patch("django.contrib.auth.get_user_model")
@TASK_PATCH
def test_falls_back_to_username_lookup(
    mock_task,
    mock_get_model,
    _mock_validate,  # noqa: PT019
):
    """When email is empty, resolve it from the username."""
    mock_user = mock.MagicMock()
    mock_user.email = "resolved@example.com"
    mock_get_model.return_value.objects.get.return_value = mock_user

    role_data = _make_role_data(email="", username="staffuser", role="staff")

    handle_course_access_role_added(
        sender=None,
        course_access_role_data=role_data,
    )

    mock_get_model.return_value.objects.get.assert_called_once_with(
        username="staffuser"
    )
    mock_task.delay.assert_called_once_with(
        user_email="resolved@example.com",
        course_key=COURSE_KEY,
        role="staff",
    )


@VALID_WEBHOOK_PATCH
@mock.patch("django.contrib.auth.get_user_model")
@TASK_PATCH
def test_skips_when_username_not_found(
    mock_task,
    mock_get_model,
    _mock_validate,  # noqa: PT019
):
    """Should skip webhook if neither email nor user exists."""
    MockUser = mock_get_model.return_value
    MockUser.DoesNotExist = Exception
    MockUser.objects.get.side_effect = MockUser.DoesNotExist

    role_data = _make_role_data(email="", username="ghost", role="staff")

    handle_course_access_role_added(
        sender=None,
        course_access_role_data=role_data,
    )

    mock_task.delay.assert_not_called()


@mock.patch(
    "ol_openedx_events_handler.utils.validate_enrollment_webhook",
    return_value=False,
)
@TASK_PATCH
def test_skips_when_webhook_not_configured(
    mock_task,
    _mock_validate,  # noqa: PT019
):
    """Should skip entirely when webhook is not configured."""
    role_data = _make_role_data(role="instructor")

    handle_course_access_role_added(
        sender=None,
        course_access_role_data=role_data,
    )

    mock_task.delay.assert_not_called()
