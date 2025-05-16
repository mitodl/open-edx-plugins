"""Django Signal handlers."""

import logging

from django.contrib.auth import get_user_model
from lms.djangoapps.courseware.courses import get_course_by_id
from ol_openedx_canvas_integration.client import CanvasClient, update_grade_payload_kv
from ol_openedx_canvas_integration.utils import get_canvas_course_id
from ol_openedx_canvas_integration.api import get_subsection_grade_for_user

log = logging.getLogger(__name__)

USER_MODEL = get_user_model()


def update_grade_in_canvas(sender, instance, created, **kwargs):
    """
    Automatically update grades in Canvas when assignments are synced.

    This signal reciever is wired to the `post_save` signal from the
    lms.djangoapps.grades.models.PersistentSubsectionGrade model. It then
    updates Canvas course if the subsection is already synced to a Canvas
    course as an assignment.
    """
    course = get_course_by_id(instance.course_id)
    canvas_course_id = get_canvas_course_id(course)
    if not canvas_course_id:
        log.debug("Canvas course ID not found. Skipping grade sync.")
        return

    log.info("Canvas Integration: Attempting to sync grade.")

    client = CanvasClient(canvas_course_id=canvas_course_id)
    existing_assignments_map = client.get_assignments_by_int_id()
    log.info("Existing assignments map: %s", existing_assignments_map)

    log.info("Full usage key: %s", instance.full_usage_key)
    if not str(instance.full_usage_key) in existing_assignments_map:
        log.warning("The assignement %s is not synced with canvas skipping.", instance.usage_key)
        return

    canvas_assignment_id = existing_assignments_map[str(instance.usage_key)]
    openedx_user = USER_MODEL.objects.get(id=instance.user_id)
    canvas_user_id = client.get_student_id_by_email(openedx_user.email)
    if not canvas_user_id:
        log.warning("The user %s is not enrolled in Canvas.", openedx_user)
        return

    # NOTE, theoritically we could simply use the values from the ``instance``.
    # However, the grade calculation seems a bit more complicated with overrides.
    # So, this uses the CourseGrade Python API.
    grade = get_subsection_grade_for_user(instance.course_id, instance.full_usage_key, instance.user_id)
    if not grade:
        log.error("Couldn't get grade for subsection <%s> with user <%s>", instance.full_usage_key, instance.user_id)
        return

    payload = dict([update_grade_payload_kv(canvas_user_id, grade.percent_graded)])
    res = client.update_assignment_grades(canvas_assignment_id, payload)

    if res.status_code != 200:
        log.error("Canvas Integration: Grade Synced failed. HTTP Status: %s", res.status_code)
        return

    log.info("Canvas Integration: Grade synced successfully.")
