"""
Module containing the Celery tasks that are called from the CMS.

This module ideally should be merged with tasks.py. However, tasks.py
contains references to settings which are not present in the 'cms'.
Since cms dynamically loads handlers.py via ready() in app config,
making handler.py depend on tasks.py results in initialization failures.
So, this module has been added without any dependencies on LMS only
settings.
"""

from __future__ import annotations

import logging

import requests
from celery import shared_task
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from lms.djangoapps.courseware.courses import get_course_by_id
from lms.djangoapps.instructor.views.tools import set_due_date_extension
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import ItemNotFoundError

from ol_openedx_canvas_integration.api import course_graded_items
from ol_openedx_canvas_integration.client import CanvasClient, create_assignment_payload
from ol_openedx_canvas_integration.utils import (
    get_canvas_course_id,
    is_canvas_dates_sync_enabled,
)

logger = logging.getLogger(__name__)
TASK_LOG = logging.getLogger("edx.celery.task")
User = get_user_model()


def diff_assignments(
    openedx_assignments,
    canvas_assignments_map,
    use_canvas_dates=False,  # noqa: FBT002
):
    """Perform a diff between the assignments in Canvas and Open edX.

    Args:
        openedx_assignments (list): List of Open edX subsection objects
        canvas_assignments_map (dict): Map of assignment integration IDs to Canvas
                                       assignment IDs
        use_canvas_dates (bool): Whether to sync the due dates of the assignments
                                 with the due dates of the subsections

    Returns:
        dict: The diff between the assignments with the following structure:
            {
                "add": [dict]: List of assignment payloads to be created in Canvas,
                "update": {int: dict}: Map of Canvas IDs to assignment payloads,
                "delete": [int]: List of Canvas assignment IDs to delete
            }
    """
    assignment_diff = {"add": [], "update": {}, "delete": []}
    for subsection in openedx_assignments:
        integration_id = str(subsection.location)
        payload = create_assignment_payload(
            subsection, use_canvas_dates=use_canvas_dates
        )
        canvas_assignment = canvas_assignments_map.pop(integration_id, None)
        if canvas_assignment:
            # if the assignment exists in Canvas, remove from the map to indicate
            # it's synced.
            payload["assignment"]["published"] = canvas_assignment.get(
                "is_published", False
            )
            assignment_diff["update"][canvas_assignment["id"]] = payload
        else:
            assignment_diff["add"].append(payload)

    # any left over assignments in the map is considered as deleted in Open edX
    assignment_diff["delete"] = [c["id"] for c in canvas_assignments_map.values()]

    return assignment_diff


def add_assignments(canvas, assignment_payloads: list[dict]):
    """Add new assignments in Canvas from provided Open edX assignments.

    Args:
        canvas: Canvas client instance used to interact with the Canvas API
        assignment_payloads (list[dict]): List of Canvas assignment payload dict
    """

    succeeded = 0
    for payload in assignment_payloads:
        res = canvas.create_canvas_assignment(payload)
        try:
            res.raise_for_status()
            succeeded += 1
        except requests.HTTPError as e:
            logger.warning(
                "Failed to create new assignment for subsection: %s. Error: %s",
                payload["assignment"]["integration_id"],
                str(e),
            )
    if succeeded:
        logger.info(
            "%d of %d new assignments were successfully added in Canvas.",
            succeeded,
            len(assignment_payloads),
        )


def update_assignments(canvas, assignment_map: dict[int, dict]):
    """Update existing assignments in Canvas with the latest data.

    Args:
        canvas: Canvas client instance used to interact with the Canvas API
        assignment_map (dict[int, dict]): Map of Canvas assignment IDs to payload dicts
    """
    succeeded = 0
    for canvas_id, payload in assignment_map.items():
        res = canvas.update_canvas_assignment(canvas_id, payload)
        try:
            res.raise_for_status()
            succeeded += 1
        except requests.HTTPError as e:
            logger.warning(
                "Failed to update Canvas Assignment %d. Error: %s", canvas_id, str(e)
            )
    if succeeded:
        logger.info(
            "%d of %d assignments were successfully updated in Canvas.",
            succeeded,
            len(assignment_map),
        )


def delete_assignments(canvas, assignment_ids: list[int]):
    """Delete given assignments from Canvas.

    Args:
        canvas: Canvas client instance used to interact with the Canvas API
        assignment_ids (list[int]): List of Canvas assignment IDs to delete
    """
    succeeded = 0
    for canvas_id in assignment_ids:
        res = canvas.delete_canvas_assignment(canvas_id)
        try:
            res.raise_for_status()
            succeeded += 1
        except requests.HTTPError as e:
            logger.warning(
                "Failed to delete Canvas assignment: %d. Error %s", canvas_id, str(e)
            )
    if succeeded:
        logger.info(
            "%d for %d assignments were successfully deleted in Canvas.",
            succeeded,
            len(assignment_ids),
        )


@shared_task
def sync_course_assignments_with_canvas(course_id):
    """
    Sync the assignments in the course with Canvas if there is a linked Canvas course.

    Args:
        course_id (str): Open edX Course ID
    """
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    canvas_course_id = get_canvas_course_id(course)
    use_canvas_due_dates = is_canvas_dates_sync_enabled(course)

    if not canvas_course_id:
        logger.info(
            "Course %s is not mapped to a Canvas Course. Skipping assignment sync.",
            course_id,
        )
        return

    openedx_assignments = [
        item["subsection_block"] for _, item, _ in course_graded_items(course)
    ]
    canvas = CanvasClient(canvas_course_id=canvas_course_id)
    canvas_assignments = canvas.get_canvas_assignments()

    operations_map = diff_assignments(
        openedx_assignments, canvas_assignments, use_canvas_due_dates
    )
    logger.info(
        "Syncing assignments with Canvas. Adding: %d, Updating: %d, Deleting: %d",
        len(operations_map["add"]),
        len(operations_map["update"]),
        len(operations_map["delete"]),
    )

    add_assignments(canvas, operations_map["add"])
    update_assignments(canvas, operations_map["update"])
    delete_assignments(canvas, operations_map["delete"])


@shared_task
def sync_canvas_due_dates(course_id: str):
    """
    Synchronize due dates for the specified course with the Canvas platform.

    This task is a wrapper around the `_sync_canvas_due_dates` function, which
    performs the actual synchronization of assignment due dates from Canvas to
    the platform.

    Parameters:
        course_id (str): The unique identifier of the course whose due
        dates need to be synchronized.
    """
    _sync_canvas_due_dates(course_id)


def sync_canvas_due_date_extensions(client, course, block, overrides):
    """
    Synchronize due date extensions for students in Canvas with the platform.

    Parameters:
        client (CanvasAPIClient): The Canvas API client for making requests.
        course (Course): Course object for which due date extensions are being synced.
        block (Block): Block object for which due date extensions are being synced.
        overrides (list): List of due date overrides from Canvas.
    """
    if not overrides:
        return
    canvas_course_id = get_canvas_course_id(course)
    for override in overrides:
        if "student_ids" in override:
            emails = client.get_emails_by_student_ids(override["student_ids"])
            students = User.objects.filter(email__in=emails)
            for student in students:
                TASK_LOG.info(
                    "Due Date Sync: Syncing due date for student %s in course %s",
                    student.id,
                    course.id,
                )
                due_date_override = parse_datetime(override["due_at"])
                set_due_date_extension(
                    course,
                    block,
                    student,
                    due_date_override,
                    reason=f"Synced from canvas course: {canvas_course_id}",
                )


def _sync_canvas_due_dates(course_id: str):
    """
    Synchronize assignment due dates from Canvas to a specific course in the platform.

    This function retrieves assignment due dates from Canvas associated with a
    given course and updates the platform's course content accordingly. The
    function skips synchronization if the course has no Canvas ID or if using
    Canvas due dates is disabled for the course.

    Arguments:
        course_id (str): The unique identifier of the course to be synchronized.
    """
    course_key = CourseKey.from_string(course_id)
    course = get_course_by_id(course_key)
    canvas_course_id = get_canvas_course_id(course)
    if not canvas_course_id:
        TASK_LOG.info(
            "Due Date Sync: No canvas ID. Skipped for course %s",
            course_id,
        )
        return
    use_canvas_due_dates = is_canvas_dates_sync_enabled(course)
    if not use_canvas_due_dates:
        TASK_LOG.info(
            "Due Date Sync: Disabled. Skipped for course %s",
            course_id,
        )
        return

    TASK_LOG.info(
        "Due Date Sync: Starting for course %s with canvas course id: %s",
        course_id,
        canvas_course_id,
    )

    client = CanvasClient(canvas_course_id=canvas_course_id)
    canvas_assignments = client.get_canvas_assignments()

    with modulestore().bulk_operations(course_key):
        for usage_id, canvas_assignment in canvas_assignments.items():
            try:
                usage_key = UsageKey.from_string(usage_id)
                due_at = canvas_assignment.get("due_at")
                block = modulestore().get_item(usage_key)
                sync_canvas_due_date_extensions(
                    client, course, block, canvas_assignment.get("overrides")
                )
                if due_at:
                    block.due = parse_datetime(due_at)
                else:
                    block.due = None
                modulestore().update_item(block, ModuleStoreEnum.UserID.mgmt_command)
            except ItemNotFoundError:
                TASK_LOG.error(
                    "Due Date Sync: Error updating due date for %s: block not found.",
                    usage_id,
                )
            except InvalidKeyError:
                TASK_LOG.error(
                    "Due Date Sync: Error updating due date for %s: invalid key.",
                    usage_id,
                )
            except Exception as e:  # noqa: BLE001
                TASK_LOG.error(
                    "Due Date Sync: Error updating due date for %s: %s", usage_id, e
                )
