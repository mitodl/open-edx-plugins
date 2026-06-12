"""DRF views for ol_openedx_feedback."""

import logging

from edx_rest_framework_extensions.auth.jwt.authentication import JwtAuthentication
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.lib.api.authentication import BearerAuthentication
from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListCreateAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ol_openedx_feedback.events import emit_feedback_event
from ol_openedx_feedback.models import BlockFeedback
from ol_openedx_feedback.serializers import (
    FeedbackCreateSerializer,
    FeedbackReadSerializer,
)
from ol_openedx_feedback.utils import get_course_title

log = logging.getLogger(__name__)


class FeedbackPagination(PageNumberPagination):
    """Pagination for the feedback read endpoint."""

    page_size = 100
    page_size_query_param = "page_size"
    max_page_size = 1000


class FeedbackSubmissionView(ListCreateAPIView):
    """POST: authenticated learners submit feedback. GET: staff/services read it."""

    authentication_classes = (
        JwtAuthentication,
        BearerAuthentication,
        SessionAuthentication,
    )
    pagination_class = FeedbackPagination

    def get_permissions(self):
        """Learners may POST; only staff/services may read."""
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [IsAdminUser()]

    def get_serializer_class(self):
        """Use the create serializer for writes and the read serializer for reads."""
        if self.request.method == "POST":
            return FeedbackCreateSerializer
        return FeedbackReadSerializer

    def get_queryset(self):
        """Return feedback, optionally filtered by course, block, or date."""
        qs = BlockFeedback.objects.select_related("user").all()
        course_id = self.request.query_params.get("course_id")
        block_usage_key = self.request.query_params.get("block_usage_key")
        # ISO date for ETL/incremental pulls by consuming services.
        since = self.request.query_params.get("since")
        if course_id:
            try:
                qs = qs.filter(course_id=CourseKey.from_string(course_id))
            except InvalidKeyError:
                qs = qs.none()
        if block_usage_key:
            try:
                qs = qs.filter(block_usage_key=UsageKey.from_string(block_usage_key))
            except InvalidKeyError:
                qs = qs.none()
        if since:
            qs = qs.filter(created__gte=since)
        return qs

    def create(self, request, *args, **kwargs):  # noqa: ARG002
        """Persist a submission, resolve the course title, and emit an event."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # course_title is resolved server-side, never trusted from the client.
        course_title = get_course_title(serializer.validated_data["course_id"])
        feedback = serializer.save(user=request.user, course_title=course_title)
        emit_feedback_event(feedback)
        return Response(FeedbackReadSerializer(feedback).data, status=201)
