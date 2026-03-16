"""
Views for the public Course Outline API (Learn product page modules).
"""

from django.core.cache import cache
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.permissions import IsAdminUser
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.authentication import SessionAuthentication
from xmodule.modulestore.django import modulestore

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from openedx.core.lib.api.authentication import BearerAuthentication
from openedx.core.lib.api.view_utils import DeveloperErrorViewMixin, verify_course_exists
from lms.djangoapps.course_api.blocks.api import get_blocks
from openedx.features.effort_estimation.block_transformers import EffortEstimationTransformer
from ol_openedx_course_outline_api.constants import (
    COURSE_OUTLINE_CACHE_KEY_PREFIX,
    COURSE_OUTLINE_CACHE_TIMEOUT_SECONDS,
)
from ol_openedx_course_outline_api.utils import build_modules_from_blocks


class CourseOutlineView(DeveloperErrorViewMixin, GenericAPIView):
    """
    Public API that returns course outline (modules) for the Learn product page.

    GET api/course-outline/v0/{course_id}/

    Returns course_id, generated_at, and a list of modules (chapters)
    with title, effort_time, effort_activities, and counts (videos, readings, assignments, app_items).

    effort_time comes from the platform's EffortEstimationTransformer (see
    openedx/features/effort_estimation). Configure course publish, video durations, and
    waffle flag so the Blocks API returns non-zero effort_time; see plugin README.
    """

    http_method_names = ["get"]
    permission_classes = [IsAdminUser]
    authentication_classes = (
        JwtAuthentication,
        BearerAuthentication,
        SessionAuthentication,
    )

    @verify_course_exists()
    def get(self, request, course_id):
        from datetime import datetime, timezone as dt_tz

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

        # Per-course cache: only when response is not user-specific (no gating).
        cache_key = f"{COURSE_OUTLINE_CACHE_KEY_PREFIX}{course_key}"
        cached = cache.get(cache_key)
        if cached is not None:
            cached["generated_at"] = datetime.now(dt_tz.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            )
            return Response(cached, status=status.HTTP_200_OK)

        requested_fields = [
            "children",
            "type",
            "display_name",
            "graded",
            "format",  # assignment type (Homework, etc.); used as fallback when graded is False
            "visible_to_staff_only",
            EffortEstimationTransformer.EFFORT_TIME,
        ]

        blocks_response = get_blocks(
            request,
            course.location,
            user=None,
            depth=None,  # full tree so units and their video/problem/html blocks are included
            requested_fields=requested_fields,
        )

        root_id = blocks_response.get("root")
        blocks_data = blocks_response.get("blocks") or {}
        modules = build_modules_from_blocks(blocks_data, root_id)

        response_data = {
            "course_id": str(course_key),
            "generated_at": datetime.now(dt_tz.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "modules": modules,
        }

        cache_key = f"{COURSE_OUTLINE_CACHE_KEY_PREFIX}{course_key}"
        cache.set(
            cache_key,
            dict(response_data),
            COURSE_OUTLINE_CACHE_TIMEOUT_SECONDS,
        )

        return Response(response_data, status=status.HTTP_200_OK)
