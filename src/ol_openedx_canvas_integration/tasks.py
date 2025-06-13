"""Tasks for canvas"""

import hashlib
import logging
from functools import partial

import requests
from celery import shared_task
from django.contrib.auth import get_user_model
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.grades.models import PersistentSubsectionGrade
from lms.djangoapps.instructor_task.api_helper import submit_task
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask
from lms.djangoapps.instructor_task.tasks_helper.runner import run_main_task

from ol_openedx_canvas_integration import task_helpers
from ol_openedx_canvas_integration.api import get_subsection_user_grades
from ol_openedx_canvas_integration.client import CanvasClient, update_grade_payload_kv
from ol_openedx_canvas_integration.constants import (
    TASK_TYPE_PUSH_EDX_GRADES_TO_CANVAS,
    TASK_TYPE_SYNC_CANVAS_ENROLLMENTS,
)
from ol_openedx_canvas_integration.utils import get_canvas_course_id

TASK_LOG = logging.getLogger("edx.celery.task")
USER_MODEL = get_user_model()


def run_sync_canvas_enrollments(
    request, course_key, canvas_course_id, unenroll_current
):
    """
    Submit a task to start syncing canvas enrollments
    """
    task_type = TASK_TYPE_SYNC_CANVAS_ENROLLMENTS
    task_class = sync_canvas_enrollments_task
    task_input = {
        "course_key": course_key,
        "canvas_course_id": canvas_course_id,
        "unenroll_current": unenroll_current,
    }
    task_key = hashlib.md5(course_key.encode("utf8")).hexdigest()  # noqa: S324
    TASK_LOG.debug("Submitting task to sync canvas enrollments")
    return submit_task(request, task_type, task_class, course_key, task_input, task_key)


@shared_task(base=BaseInstructorTask)
def sync_canvas_enrollments_task(entry_id, xmodule_instance_args):
    """
    Fetch enrollments from canvas and update
    """
    action_name = "sync_canvas_enrollments"
    TASK_LOG.info("Running task to sync Canvas enrollments")
    task_fn = partial(task_helpers.sync_canvas_enrollments, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


def run_push_edx_grades_to_canvas(request, course_id):
    """
    Submit a task to start pushing edX grades to Canvas
    """
    task_type = TASK_TYPE_PUSH_EDX_GRADES_TO_CANVAS
    task_class = push_edx_grades_to_canvas_task
    task_input = {
        # course_key is already passed into the task, but we need to put it in task_input as well  # noqa: E501
        # so the instructor task status can be properly calculated instead of being marked incomplete  # noqa: E501
        "course_key": str(course_id)
    }
    task_key = hashlib.md5(course_id.encode("utf8")).hexdigest()  # noqa: S324
    TASK_LOG.debug("Submitting task to push edX grades to Canvas")
    return submit_task(request, task_type, task_class, course_id, task_input, task_key)


@shared_task(base=BaseInstructorTask)
def push_edx_grades_to_canvas_task(entry_id, xmodule_instance_args):
    """
    Push edX grades to Canvas
    """
    action_name = "push_edx_grades_to_canvas"
    TASK_LOG.info("Running task to push edX grades to Canvas")
    task_fn = partial(task_helpers.push_edx_grades_to_canvas, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


@shared_task
def sync_user_grade_with_canvas(grade_id):
    """
    Call the Canvas API and update the user's grade.
    """
    grade_instance = PersistentSubsectionGrade.objects.get(id=grade_id)
    course = get_course_by_id(grade_instance.course_id)
    canvas_course_id = get_canvas_course_id(course)
    if not canvas_course_id:
        TASK_LOG.debug("Canvas course ID not found. Skipping grade sync.")
        return

    TASK_LOG.info(
        "Course %s linked to Canvas Course %s. Attempting to sync grade.",
        grade_instance.course_id,
        canvas_course_id,
    )

    client = CanvasClient(canvas_course_id=canvas_course_id)
    existing_assignments_map = client.get_assignments_by_int_id()

    if str(grade_instance.full_usage_key) not in existing_assignments_map:
        TASK_LOG.warning(
            "The assignment %s is not synced with Canvas. Skipping grade sync.",
            grade_instance.usage_key,
        )
        return

    canvas_assignment_id = existing_assignments_map[str(grade_instance.usage_key)]
    openedx_user = USER_MODEL.objects.get(id=grade_instance.user_id)
    canvas_user_id = client.get_student_id_by_email(openedx_user.email)
    if not canvas_user_id:
        TASK_LOG.warning("The user %s is not enrolled in Canvas.", openedx_user)
        return

    # NOTE, theoretically we could simply use grade points from the ``grade_instance``.
    # However, the grade calculation seems a bit more complicated with overrides.
    # So, this uses the CourseGrade Python API.
    grade_dict = get_subsection_user_grades(
        course, grade_instance.full_usage_key, openedx_user
    )
    try:
        grade = grade_dict[grade_instance.full_usage_key][openedx_user]
        payload = dict([update_grade_payload_kv(canvas_user_id, grade.percent_graded)])
    except (KeyError, AttributeError):
        TASK_LOG.error(
            "Couldn't get grade for subsection <%s> with user <%s>",
            grade_instance.full_usage_key,
            grade_instance.user_id,
        )
        return

    res = client.update_assignment_grades(canvas_assignment_id, payload)

    if res.status_code != requests.codes.ok:
        TASK_LOG.error(
            "Canvas Integration: Grade Synced failed. HTTP Status: %s", res.status_code
        )
        return

    TASK_LOG.info("Canvas Integration: Grade synced successfully.")
