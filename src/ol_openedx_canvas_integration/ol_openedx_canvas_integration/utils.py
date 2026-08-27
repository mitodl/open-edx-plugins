"""Utilities for Canvas plugin"""

import logging

from django.conf import settings
from django.core.cache import cache
from django.http import Http404
from lms.djangoapps.courseware.courses import get_course_by_id

log = logging.getLogger(__name__)

CANVAS_COURSE_ID_CACHE_KEY_TEMPLATE = "canvas_course_id:{course_id}"
_MISSING = object()


def get_canvas_course_id(course=None):
    """Get the course Id from the course settings"""
    return course.other_course_settings.get("canvas_id") if course else None


def is_canvas_dates_sync_enabled(course=None):
    """Get the canvas due dates setting from the course settings"""
    return course and course.other_course_settings.get("use_canvas_due_dates", False)


def get_cached_canvas_course_id(course_id):
    """
    Return the Canvas course id linked to ``course_id``, using a short-lived cache.

    Both outcomes (linked / not linked) are cached, so repeated grade saves for the
    same course don't each force a full modulestore course load. Any failure in the
    lookup or cache access is caught so it can never propagate out of the
    ``post_save`` signal receiver that calls this. A failure to *read or write* the
    cache is treated as a cache miss / no-op rather than "not linked", so a cache
    outage can never cause a Canvas-linked course to be treated as unlinked. Only a
    genuine "course not found" is treated as (and cached as) "not linked" -- any
    other lookup failure (e.g. a transient modulestore/DB error) returns None
    without caching, so it's retried on the next grade save instead of being
    conflated with a real unlink.
    """
    cache_key = CANVAS_COURSE_ID_CACHE_KEY_TEMPLATE.format(course_id=course_id)

    try:
        cached_value = cache.get(cache_key, _MISSING)
    except Exception:
        log.warning(
            "Could not read cached Canvas course id for %s", course_id, exc_info=True
        )
        cached_value = _MISSING

    if cached_value is not _MISSING:
        return cached_value

    try:
        course = get_course_by_id(course_id)
    except Http404:
        log.warning(
            "Could not determine Canvas course id for %s: course not found",
            course_id,
        )
        canvas_course_id = None
    except Exception:
        log.exception("Unexpected error determining Canvas course id for %s", course_id)
        return None
    else:
        canvas_course_id = get_canvas_course_id(course)

    try:
        cache.set(cache_key, canvas_course_id, settings.CANVAS_COURSE_ID_CACHE_TIMEOUT)
    except Exception:
        log.warning("Could not cache Canvas course id for %s", course_id, exc_info=True)

    return canvas_course_id


def get_task_output_formatted_message(task_output):
    """Take the edX task output and format a message for table display on task result"""
    # this reports on actions for a course as a whole
    results = task_output.get("results", {})
    assignments_count = results.get("assignments", 0)
    grades_count = results.get("grades", 0)

    return (
        f"{grades_count} grades and {assignments_count} assignments updated or created"
    )
