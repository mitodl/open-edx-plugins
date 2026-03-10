"""Tests for the COURSE_ACCESS_ROLE_ADDED signal receiver."""

from unittest import mock

from django.test import TestCase, override_settings
from ol_openedx_course_staff_webhook.signals import (
    listen_for_course_access_role_added,
)


def _make_role_data(
    *,
    email="staff@example.com",
    course_key="course-v1:MITx+1.001x+2025_T1",
    role="instructor",
):
    """Build a mock CourseAccessRoleData object."""
    user_pii = mock.MagicMock()
    user_pii.email = email
    user_pii.username = email.split("@")[0]

    user = mock.MagicMock()
    user.pii = user_pii

    role_data = mock.MagicMock()
    role_data.user = user
    role_data.course_key = course_key
    role_data.org_key = "MITx"
    role_data.role = role
    return role_data


class TestListenForCourseAccessRoleAdded(TestCase):
    """Tests for listen_for_course_access_role_added signal receiver."""

    @mock.patch(
        "ol_openedx_course_staff_webhook.signals"
        ".notify_course_staff_addition"
    )
    def test_triggers_task_for_instructor_role(self, mock_task):
        """Task should be triggered when an instructor role is added."""
        role_data = _make_role_data(role="instructor")

        listen_for_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

        mock_task.delay.assert_called_once_with(
            user_email="staff@example.com",
            course_key="course-v1:MITx+1.001x+2025_T1",
            role="instructor",
        )

    @mock.patch(
        "ol_openedx_course_staff_webhook.signals"
        ".notify_course_staff_addition"
    )
    def test_triggers_task_for_staff_role(self, mock_task):
        """Task should be triggered when a staff role is added."""
        role_data = _make_role_data(role="staff")

        listen_for_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

        mock_task.delay.assert_called_once_with(
            user_email="staff@example.com",
            course_key="course-v1:MITx+1.001x+2025_T1",
            role="staff",
        )

    @mock.patch(
        "ol_openedx_course_staff_webhook.signals"
        ".notify_course_staff_addition"
    )
    def test_ignores_non_staff_roles(self, mock_task):
        """Task should NOT be triggered for roles not in the allowed list."""
        role_data = _make_role_data(role="beta_testers")

        listen_for_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

        mock_task.delay.assert_not_called()

    @override_settings(
        MITXONLINE_COURSE_STAFF_ROLES=[
            "instructor",
            "staff",
            "data_researcher",
        ]
    )
    @mock.patch(
        "ol_openedx_course_staff_webhook.signals"
        ".notify_course_staff_addition"
    )
    def test_respects_custom_roles_setting(self, mock_task):
        """Custom roles in settings should trigger task."""
        role_data = _make_role_data(role="data_researcher")

        listen_for_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

        mock_task.delay.assert_called_once_with(
            user_email="staff@example.com",
            course_key="course-v1:MITx+1.001x+2025_T1",
            role="data_researcher",
        )

    @override_settings(MITXONLINE_COURSE_STAFF_ROLES=["instructor"])
    @mock.patch(
        "ol_openedx_course_staff_webhook.signals"
        ".notify_course_staff_addition"
    )
    def test_ignores_staff_when_not_in_custom_roles(
        self, mock_task
    ):
        """Task should NOT trigger for excluded roles."""
        role_data = _make_role_data(role="staff")

        listen_for_course_access_role_added(
            sender=None,
            course_access_role_data=role_data,
        )

        mock_task.delay.assert_not_called()
