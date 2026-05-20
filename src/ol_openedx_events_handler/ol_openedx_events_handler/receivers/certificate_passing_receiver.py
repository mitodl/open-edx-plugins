"""Django Signal handlers."""

import logging

from common.djangoapps.course_modes import api as modes_api
from common.djangoapps.student.models import CourseEnrollment
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.data import CertificatesDisplayBehaviors

from ol_openedx_events_handler.tasks import (
    create_certificate_for_passing_grade,
)
from ol_openedx_events_handler.utils import validate_certificate_webhook

log = logging.getLogger(__name__)


def _is_eligible_for_certificate(user, course_id):
    """
    Determine whether certificate generation should be triggered.
    """
    enrollment_mode, is_active = CourseEnrollment.enrollment_mode_for_user(
        user, course_id
    )

    if not is_active:
        return False

    is_mode_eligible_for_cert = modes_api.is_eligible_for_certificate(enrollment_mode)
    course_overview = CourseOverview.get_from_id(course_id)
    certificate_display_behavior = course_overview.certificates_display_behavior

    return is_mode_eligible_for_cert and (
        course_overview.self_paced
        or certificate_display_behavior == CertificatesDisplayBehaviors.EARLY_NO_INFO
    )


def listen_for_passing_grade(sender, user, course_id, **kwargs):  # noqa: ARG001
    """
    Automatically create a certificate in the relevant MIT application when a user
    completes a course and gets a passing grade.
    """

    if not _is_eligible_for_certificate(user, course_id):
        return

    if not validate_certificate_webhook():
        return

    course_key = str(course_id)
    user_email = getattr(user, "email", None)
    if not user_email and getattr(user, "pii", None):
        user_email = getattr(user.pii, "email", None)
    if not user_email:
        log.error(
            "Cannot dispatch certificate webhook without user email for course '%s'.",
            course_key,
        )
        return

    log.info(
        "User '%s' passed course '%s'. Dispatching certificate webhook.",
        user_email,
        course_key,
    )
    create_certificate_for_passing_grade.delay(
        user_email=user_email,
        course_key=course_key,
    )
