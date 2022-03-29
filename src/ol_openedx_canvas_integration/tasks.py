"""Tasks for canvas"""
import hashlib
import logging
from functools import partial

from celery import shared_task
from lms.djangoapps.instructor_task.api_helper import submit_task
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask
from lms.djangoapps.instructor_task.tasks_helper.runner import run_main_task

from ol_openedx_canvas_integration import task_helpers
from ol_openedx_canvas_integration.constants import (
    TASK_TYPE_PUSH_EDX_GRADES_TO_CANVAS,
    TASK_TYPE_SYNC_CANVAS_ENROLLMENTS,
)

TASK_LOG = logging.getLogger("edx.celery.task")


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
    task_key = hashlib.md5(course_key.encode("utf8")).hexdigest()
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
        # course_key is already passed into the task, but we need to put it in task_input as well
        # so the instructor task status can be properly calculated instead of being marked incomplete
        "course_key": str(course_id)
    }
    task_key = hashlib.md5(course_id.encode("utf8")).hexdigest()
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
