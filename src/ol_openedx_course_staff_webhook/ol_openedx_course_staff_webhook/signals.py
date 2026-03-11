"""Signal receivers for the course staff webhook plugin."""

import logging

from django.conf import settings

from ol_openedx_course_staff_webhook.tasks import (
    notify_course_staff_addition,
)

log = logging.getLogger(__name__)


def listen_for_course_access_role_added(
    sender,  # noqa: ARG001
    course_access_role_data,
    **kwargs,  # noqa: ARG001
):
    """
    Handle the COURSE_ACCESS_ROLE_ADDED signal.

    When a user is assigned a course access role (e.g., instructor or staff),
    this receiver triggers an asynchronous task to notify MITx Online so the
    user can be enrolled as an auditor in the corresponding course.

    Args:
        sender: The sender of the signal.
        course_access_role_data (CourseAccessRoleData): Data about the role
            assignment, including user info, course key, org, and role.
        **kwargs: Additional keyword arguments from the signal.
    """
    allowed_roles = getattr(
        settings,
        "MITXONLINE_COURSE_STAFF_ROLES",
        ["instructor", "staff"],
    )

    role = course_access_role_data.role
    if role not in allowed_roles:
        log.debug(
            "Ignoring role '%s' for user in course %s — not in allowed roles %s",
            role,
            course_access_role_data.course_key,
            allowed_roles,
        )
        return

    user_email = course_access_role_data.user.pii.email
    course_key = str(course_access_role_data.course_key)

    log.info(
        "Course access role '%s' added for user '%s' in course '%s'. "
        "Notifying MITx Online.",
        role,
        user_email,
        course_key,
    )

    notify_course_staff_addition.delay(
        user_email=user_email,
        course_key=course_key,
        role=role,
    )
