"""
Module containing the Celery tasks that are called from the CMS.

This module ideally should be merged with tasks.py. However, tasks.py
contains references to settings which are not present in the 'cms'.
Since cms dynamically loads handlers.py via ready() in app config,
making handler.py depend on tasks.py results in initialization failures.
So, this module has been added without any dependencies on LMS only
settings.
"""

import logging

import requests
from celery import shared_task
from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_canvas_integration.api import course_graded_items
from ol_openedx_canvas_integration.client import CanvasClient, create_assignment_payload
from ol_openedx_canvas_integration.utils import get_canvas_course_id

logger = logging.getLogger(__name__)


def diff_assignments(openedx_assignments, canvas_assignments_map):
    """
    Peform a diff between the assignments in Canvas and Open edX.

    Args:
        openedx_assignments: List of Subsections
        canvas_assignments_map: Map of the assignment's Integration ID and Canvas ID

    Returns:
        The diff between the assignments as a dictionary of the following format:

        {
            "add": ["JSON Payload of Assignments"],
            "update": {"Map of Canvas IDs":  "JSON payload of assignments"},
            "delete": ["Integer IDs of Canvas assignments"]
        }
    """
    diff = {"add": [], "update": {}, "delete": []}

    for subsection in openedx_assignments:
        payload = create_assignment_payload(subsection)
        integration_id = str(subsection.location)

        # remove from the map to indicate it's synced
        if canvas_id := canvas_assignments_map.pop(integration_id, None):
            diff["update"][canvas_id] = payload
        else:
            diff["add"].append(payload)

    # any left over assignments in the map is considered as deleted in Open edX
    diff["delete"] = list(canvas_assignments_map.values())

    return diff


@shared_task
def sync_course_assignments_with_canvas(course_id):
    """
    Syncs the assignments in the course with Canvas if there is a linked Canvas course.

    Args:
        course_id (str): Open edX Course ID
    """
    course_key = CourseLocator.from_string(course_id)
    course = get_course_by_id(course_key)
    canvas_course_id = get_canvas_course_id(course)

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
    canvas_assignments = canvas.get_assignments_by_int_id()

    operations_map = diff_assignments(openedx_assignments, canvas_assignments)
    logger.info(
        "Syncing assignments with Canvas. Adding: %d, Updating: %d, Deleting: %d",
        len(operations_map["add"]),
        len(operations_map["update"]),
        len(operations_map["delete"]),
    )

    succeeded = 0
    for payload in operations_map["add"]:
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
    if operations_map["add"]:
        logger.info(
            "%d of %d new assignments were successfully added in Canvas.",
            succeeded,
            len(operations_map["add"]),
        )

    succeeded = 0
    for canvas_id, payload in operations_map["update"].items():
        res = canvas.update_canvas_assignment(canvas_id, payload)
        try:
            res.raise_for_status()
            succeeded += 1
        except requests.HTTPError as e:
            logger.warning(
                "Failed to update Canvas Assignment %d. Error: %s", canvas_id, str(e)
            )
    if operations_map["update"]:
        logger.info(
            "%d of %d assignments were successfully updated in Canvas.",
            succeeded,
            len(operations_map["update"]),
        )

    succeeded = 0
    for canvas_id in operations_map["delete"]:
        res = canvas.delete_canvas_assignment(canvas_id)
        try:
            res.raise_for_status()
            succeeded += 1
        except requests.HTTPError as e:
            logger.warning(
                "Failed to delete Canvas assignment: %d. Error %s", canvas_id, str(e)
            )
    if operations_map["delete"]:
        logger.info(
            "%d for %d assignments were successfully deleted in Canvas.",
            succeeded,
            len(operations_map["delete"]),
        )
