"""
Views for the public Course Outline API (Learn product page modules).
"""

import hashlib
from datetime import UTC, datetime

from django.conf import settings
from django.core.cache import cache
from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from lms.djangoapps.course_api.blocks.api import get_blocks
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.block_structure.exceptions import (
    BlockStructureNotFound,
)
from openedx.core.djangoapps.content.block_structure.models import BlockStructureModel
from openedx.core.lib.api.authentication import BearerAuthentication
from openedx.core.lib.api.view_utils import (
    DeveloperErrorViewMixin,
    verify_course_exists,
)
from openedx.features.effort_estimation.block_transformers import (
    EffortEstimationTransformer,
)
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from xmodule.modulestore.django import modulestore

from ol_openedx_course_outline_api.constants import (
    COURSE_OUTLINE_CACHE_SCHEMA_VERSION,
)
from ol_openedx_course_outline_api.utils import build_modules_from_blocks


def get_collected_content_version(course):
    """
    Return the version of the collected block structure the response is built from.

    The response body comes from get_blocks(), which reads the collected block
    structure. That is rebuilt asynchronously after a publish, so the modulestore's
    course_version can already describe content the structure has not caught up to.

    Uses the same version fields the platform compares in
    BlockStructureStore.is_up_to_date, so a recollection that changes the response
    without changing course_version (a transformer version bump, for example) still
    produces a new key.

    Returns None when no collected structure exists yet. get_blocks() builds one as a
    side effect of serving the request, so there is no version that names the content
    about to be returned, and the response must not be cached.
    """
    try:
        bs_model = BlockStructureModel.get(course.location)
    except BlockStructureNotFound:
        return None

    version_data = "|".join(
        str(getattr(bs_model, field_name, None))
        for field_name in BlockStructureModel.VERSION_FIELDS
    )
    return hashlib.blake2b(version_data.encode(), digest_size=16).hexdigest()


class CourseOutlineView(DeveloperErrorViewMixin, APIView):
    """
    Return a per-chapter course outline summary.

    GET api/ol-course-outline/v0/{course_id}/
    """

    permission_classes = [IsAdminUser]
    authentication_classes = (
        JwtAuthentication,
        BearerAuthentication,
        SessionAuthentication,
    )

    @verify_course_exists()
    def get(self, request, course_id):
        """Return a course outline summary for the requested course."""
        course_key = CourseKey.from_string(course_id)

        store = modulestore()
        course = store.get_course(course_key)
        if course is None:
            raise DeveloperErrorViewMixin.api_error(
                status_code=status.HTTP_404_NOT_FOUND,
                developer_message="Course not found",
            )
        # Key changes when response logic changes (schema version) or when the
        # block structure the response is built from changes. Read the version
        # before get_blocks(), not after: reading after files this body under
        # the version of content it isn't, which is the bug. Reading before
        # can strand a newer body under the old key; that is only served again
        # if the version fields repeat, which a transformer rollback can do.
        cache_key_prefix = settings.OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX
        cache_timeout_seconds = settings.OL_COURSE_OUTLINE_API_CACHE_TIMEOUT_SECONDS
        content_version_str = get_collected_content_version(course)
        cache_key = (
            None
            if content_version_str is None
            else (
                f"{cache_key_prefix}"
                f"s{COURSE_OUTLINE_CACHE_SCHEMA_VERSION}:"
                f"{course_key}:"
                f"{content_version_str}"
            )
        )
        if cache_key is not None:
            cached = cache.get(cache_key)
            if cached is not None:
                return Response(cached, status=status.HTTP_200_OK)

        requested_fields = [
            "children",
            "type",
            "display_name",
            "graded",
            "format",  # assignment type (Homework, etc.); fallback if graded is False
            "hide_from_toc",
            "visible_to_staff_only",
            EffortEstimationTransformer.EFFORT_TIME,
            EffortEstimationTransformer.EFFORT_ACTIVITIES,
        ]

        blocks_response = get_blocks(
            request,
            course.location,
            user=None,
            depth=None,
            requested_fields=requested_fields,
        )

        root_id = blocks_response.get("root")
        blocks_data = blocks_response.get("blocks") or {}
        modules = build_modules_from_blocks(blocks_data, root_id)

        response_data = {
            "course_id": str(course_key),
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "modules": modules,
        }

        if cache_key is not None:
            cache.set(
                cache_key,
                response_data,
                cache_timeout_seconds,
            )

        return Response(response_data, status=status.HTTP_200_OK)
