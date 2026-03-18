"""Signal handler for course access role additions."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def handle_course_access_role_added(
    sender,  # noqa: ARG001
    course_access_role_data,
    **kwargs,  # noqa: ARG001
):
    """
    Handle the COURSE_ACCESS_ROLE_ADDED signal.

    When a user is assigned a course access role (e.g. instructor or staff),
    this handler triggers an asynchronous task to notify the webhook provider
    so the user can be enrolled as an auditor in the corresponding course.

    Args:
        sender: The sender of the signal.
        course_access_role_data (CourseAccessRoleData): Data about the role
            assignment, including user info, course key, org, and role.
        **kwargs: Additional keyword arguments from the signal.
    """
    from ol_openedx_events_handler.tasks.course_access_role import (  # noqa: PLC0415
        notify_course_access_role_addition,
    )
    from ol_openedx_events_handler.utils import (  # noqa: PLC0415
        validate_enrollment_webhook,
    )

    if not validate_enrollment_webhook():
        return

    allowed_roles = getattr(
        settings, "ENROLLMENT_COURSE_ACCESS_ROLES", [],
    )

    role = course_access_role_data.role
    if role not in allowed_roles:
        log.info(
            "Ignoring role '%s' for user in course %s — not in allowed roles %s",
            role,
            course_access_role_data.course_key,
            allowed_roles,
        )
        return

    user_email = course_access_role_data.user.pii.email
    if not user_email:
        from django.contrib.auth import get_user_model  # noqa: PLC0415

        username = course_access_role_data.user.pii.username
        User = get_user_model()
        try:
            user_email = User.objects.get(username=username).email
        except User.DoesNotExist:
            log.warning(
                "Cannot resolve email for username '%s'. "
                "Skipping enrollment webhook for course '%s'.",
                username,
                course_access_role_data.course_key,
            )
            return

    course_key = str(course_access_role_data.course_key)

    log.info(
        "Course access role '%s' added for user '%s' in course '%s'. "
        "Dispatching enrollment webhook.",
        role,
        user_email,
        course_key,
    )

    notify_course_access_role_addition.delay(
        user_email=user_email,
        course_key=course_key,
        role=role,
    )
