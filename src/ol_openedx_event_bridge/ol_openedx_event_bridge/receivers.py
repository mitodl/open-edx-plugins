"""Django Signal handlers."""

import logging
from http import HTTPStatus

import requests
from common.djangoapps.course_modes import api as modes_api
from common.djangoapps.student.models import CourseEnrollment
from django.conf import settings
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.data import CertificatesDisplayBehaviors

log = logging.getLogger(__name__)


def listen_for_passing_grade(sender, user, course_id, **kwargs):  # noqa: ARG001
    """
    Automatically create a certificate in the relevant MIT application when a user
    completes a course and gets a passing grade.
    """

    enrollment_mode, __ = CourseEnrollment.enrollment_mode_for_user(user, course_id)
    is_mode_eligible_for_cert = modes_api.is_eligible_for_certificate(enrollment_mode)
    course_overview = CourseOverview.get_from_id(course_id)
    certificate_display_behavior = course_overview.certificates_display_behavior
    if is_mode_eligible_for_cert and (
        course_overview.self_paced
        or certificate_display_behavior == CertificatesDisplayBehaviors.EARLY_NO_INFO
    ):
        # We should call MIT app's certificate generation API to create the certificate

        response = requests.post(
            settings.MIT_CERTIFICATE_WEBHOOK_URL,
            json={
                "user_id": user.email,
                "course_id": str(course_id),
            },
            timeout=30,
        )

        if response.status_code != HTTPStatus.OK:
            log.error(
                "Failed to create certificate for user %s in course %s. "
                "Status code: %s, Response: %s",
                user.username,
                course_id,
                response.status_code,
                response.text,
            )
        else:
            log.info(
                "Successfully created certificate for user %s in course %s.",
                user.username,
                course_id,
            )
