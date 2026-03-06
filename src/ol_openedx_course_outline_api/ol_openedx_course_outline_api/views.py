"""
Views for the public Course Outline API (Learn product page modules).
"""

import logging

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from xmodule.modulestore.django import modulestore

from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists
from lms.djangoapps.course_api.blocks.api import get_blocks
from openedx.features.effort_estimation.block_transformers import EffortEstimationTransformer
from xmodule.course_block import (
    COURSE_VISIBILITY_PUBLIC,
    COURSE_VISIBILITY_PUBLIC_OUTLINE,
)

log = logging.getLogger(__name__)

# When False, skip course visibility check so any course outline is accessible (e.g. for testing).
# When True, only public/public_outline courses are allowed, with staff bypass.
ENFORCE_PUBLIC_ACCESS = False

CONTAINER_TYPES = {"course", "chapter", "sequential", "vertical"}
KNOWN_LEAF_TYPES = {"video", "html", "problem"}

# Open edX block type (XBlock category) -> Learn API count key.
# BlockCountsTransformer returns counts keyed by category; map to our response names.
# (assignments = graded sequentials, not problem count; we count those separately.)
BLOCK_TYPE_TO_LEARN_COUNT = {
    "video": "videos",
    "html": "readings",
}
# Block types we ask the Blocks API to count (category names at block level).
BLOCK_TYPES_FOR_COUNTS = ["video", "html", "problem"]


def _get_descendant_ids(blocks_data, block_id):
    """Return set of all descendant block ids (including block_id) from blocks_data."""
    result = {block_id}
    for child_id in blocks_data.get(block_id, {}).get("children") or []:
        result.update(_get_descendant_ids(blocks_data, child_id))
    return result


def _count_assignments_under_chapter(blocks_data, chapter_id):
    """Count sequential blocks with graded=True under the chapter."""
    count = 0
    for bid in _get_descendant_ids(blocks_data, chapter_id):
        block = blocks_data.get(bid, {})
        if block.get("type") == "sequential" and block.get("graded") is True:
            count += 1
    return count


def _count_app_items_under_chapter(blocks_data, chapter_id):
    """Count leaf blocks that are not video, html, or problem (custom/app items)."""
    count = 0
    for bid in _get_descendant_ids(blocks_data, chapter_id):
        block = blocks_data.get(bid, {})
        block_type = block.get("type") or ""
        children = block.get("children") or []
        is_leaf = len(children) == 0
        if is_leaf and block_type not in CONTAINER_TYPES and block_type not in KNOWN_LEAF_TYPES:
            count += 1
    return count


def _build_modules_from_blocks(blocks_data, root_id):
    """Build list of module dicts (one per chapter) from get_blocks response."""
    modules = []
    root_block = blocks_data.get(root_id, {})
    for child_id in root_block.get("children") or []:
        block = blocks_data.get(child_id, {})
        if block.get("type") != "chapter":
            continue
        block_counts = block.get("block_counts") or {}
        counts = {"videos": 0, "readings": 0, "assignments": 0, "app_items": 0}
        for block_type, learn_key in BLOCK_TYPE_TO_LEARN_COUNT.items():
            if learn_key in counts:
                counts[learn_key] = block_counts.get(block_type, 0)
        counts["assignments"] = _count_assignments_under_chapter(blocks_data, child_id)
        counts["app_items"] = _count_app_items_under_chapter(blocks_data, child_id)
        modules.append({
            "id": child_id,
            "title": block.get("display_name") or "",
            "estimated_time_seconds": block.get("effort_time") or 0,
            "counts": counts,
        })
    return modules


class CourseOutlineView(DeveloperErrorViewMixin, GenericAPIView):
    """
    Public API that returns course outline (modules) for the Learn product page.

    GET api/course-outline/v0/{course_id}/

    Returns course_id, generated_at, and a list of modules (chapters) with title,
    estimated_time_seconds, and counts (videos, readings, assignments, app_items).

    estimated_time_seconds comes from the platform's EffortEstimationTransformer (see
    openedx/features/effort_estimation). Configure course publish, video durations, and
    waffle flag so the Blocks API returns non-zero effort_time; see plugin README.
    """

    http_method_names = ["get"]
    permission_classes = [AllowAny]

    @verify_course_exists()
    def get(self, request, course_id):
        try:
            course_key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            raise DeveloperErrorViewMixin.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message="Invalid course_id",
            )

        store = modulestore()
        course = store.get_course(course_key)
        if course is None:
            raise DeveloperErrorViewMixin.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message="Course not found",
            )

        if ENFORCE_PUBLIC_ACCESS:
            visibility = getattr(course, "course_visibility", None)
            if visibility not in (COURSE_VISIBILITY_PUBLIC, COURSE_VISIBILITY_PUBLIC_OUTLINE):
                try:
                    from lms.djangoapps.courseware.access import has_access

                    if not (
                        request.user.is_authenticated
                        and has_access(request.user, "staff", course_key).has_access
                    ):
                        raise DeveloperErrorViewMixin.api_error(
                            status_code=status.HTTP_403_FORBIDDEN,
                            developer_message="Course is not available for public outline access",
                        )
                except ImportError:
                    raise DeveloperErrorViewMixin.api_error(
                        status_code=status.HTTP_403_FORBIDDEN,
                        developer_message="Course is not available for public outline access",
                    )

        requested_fields = [
            "children",
            "type",
            "display_name",
            "graded",
            "block_counts",  # required so each block gets block_counts dict (video/html/problem at block level)
            EffortEstimationTransformer.EFFORT_TIME,
        ]
        blocks_response = get_blocks(
            request,
            course.location,
            user=None,
            depth=None,  # full tree so units and their video/problem/html blocks are included
            nav_depth=3,
            requested_fields=requested_fields,
            block_counts=BLOCK_TYPES_FOR_COUNTS,
        )

        root_id = blocks_response.get("root")
        blocks_data = blocks_response.get("blocks") or {}
        modules = _build_modules_from_blocks(blocks_data, root_id)

        from datetime import datetime, timezone as dt_tz

        return Response(
            {
                "course_id": str(course_key),
                "generated_at": datetime.now(dt_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "modules": modules,
            },
            status=status.HTTP_200_OK,
        )
