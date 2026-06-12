"""Utility helpers for ol_openedx_feedback."""

import logging

from ol_openedx_feedback.constants import EXCLUDED_BLOCK_TYPES

log = logging.getLogger(__name__)


def is_aside_applicable_to_block(block):
    """Feedback applies to every block type except structural containers."""
    block_type = getattr(block, "category", None)
    return bool(block_type) and block_type not in EXCLUDED_BLOCK_TYPES


def get_course_title(course_id):
    """Best-effort lookup of the human course title; empty string on failure."""
    try:
        from openedx.core.djangoapps.content.course_overviews.models import (  # noqa: PLC0415
            CourseOverview,
        )

        overview = CourseOverview.objects.filter(id=course_id).first()
    except Exception:
        log.exception("Could not resolve course title for %s", course_id)
        return ""
    else:
        return overview.display_name if overview else ""
