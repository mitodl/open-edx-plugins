"""
Helper functions for canvas integration tasks
"""

import datetime
from time import time

import pytz
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.instructor_task.api import get_running_instructor_tasks
from lms.djangoapps.instructor_task.models import InstructorTask
from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress

from ol_openedx_canvas_integration import api
from ol_openedx_canvas_integration.constants import CANVAS_TASK_TYPES


def sync_canvas_enrollments(
    _xmodule_instance_args,
    _entry_id,
    course_id,  # noqa: ARG001
    task_input,
    action_name,
):
    """Partial function to sync canvas enrollments"""
    start_time = time()
    num_reports = 1
    task_progress = TaskProgress(action_name, num_reports, start_time)
    api.sync_canvas_enrollments(
        course_key=task_input["course_key"],
        canvas_course_id=task_input["canvas_course_id"],
        unenroll_current=task_input["unenroll_current"],
    )
    # for simplicity, only one task update for now when everything is done
    return task_progress.update_task_state(extra_meta={"step": "Done"})


def push_edx_grades_to_canvas(
    _xmodule_instance_args,
    _entry_id,
    course_id,
    task_input,  # noqa: ARG001
    action_name,
):
    """Partial function to push edX grades to canvas"""
    start_time = time()
    num_reports = 1
    task_progress = TaskProgress(action_name, num_reports, start_time)
    course = get_course_by_id(course_id)
    grades_updated, assignments_created = api.push_edx_grades_to_canvas(course=course)
    results = {"grades": len(grades_updated), "assignments": len(assignments_created)}
    return task_progress.update_task_state(
        extra_meta={"step": "Done", "results": results}
    )


def get_filtered_instructor_tasks(course_id, user):
    """
    Return a filtered query of InstructorTasks based on the course, user, and desired
    task types
    """
    instructor_tasks = get_running_instructor_tasks(course_id)
    now = datetime.datetime.now(pytz.utc)
    filtered_tasks = InstructorTask.objects.filter(
        course_id=course_id,
        task_type__in=CANVAS_TASK_TYPES,
        updated__lte=now,
        updated__gte=now - datetime.timedelta(days=2),
        requester=user,
    ).order_by("-updated")

    return (instructor_tasks | filtered_tasks).distinct()[0:3]
