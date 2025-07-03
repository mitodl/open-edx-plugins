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
from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_canvas_integration.api import course_graded_items
from ol_openedx_canvas_integration.client import CanvasClient, create_assignment_payload
from ol_openedx_canvas_integration.utils import get_canvas_course_id

logger = logging.getLogger(__name__)


def diff_assignments(openedx_assignments, canvas_assignments_map):
    """Perform a diff between the assignments in Canvas and Open edX.

    Args:
        openedx_assignments (list): List of Open edX subsection objects
        canvas_assignments_map (dict): Map of assignment integration IDs to Canvas
                                       assignment IDs

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
        payload = create_assignment_payload(subsection)
        integration_id = str(subsection.location)

        # remove from the map to indicate it's synced
        if canvas_id := canvas_assignments_map.pop(integration_id, None):
            assignment_diff["update"][canvas_id] = payload
        else:
            assignment_diff["add"].append(payload)

    # any left over assignments in the map is considered as deleted in Open edX
    assignment_diff["delete"] = list(canvas_assignments_map.values())

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

    add_assignments(canvas, operations_map["add"])
    update_assignments(canvas, operations_map["update"])
    delete_assignments(canvas, operations_map["delete"])
