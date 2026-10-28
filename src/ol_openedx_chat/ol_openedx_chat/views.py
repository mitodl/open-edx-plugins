"""
API views for the ol_openedx_chat app.
"""

from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ol_openedx_chat.compat import get_contact_us_enabled_flag


class ContactUsEnabledView(APIView):
    """
    Report whether the Contact us launcher should be shown.

    Sample Request:
        GET /ol-openedx-chat/api/contact-us-enabled/
        GET /ol-openedx-chat/api/contact-us-enabled/{course_key}

    Sample Response:
        200 OK
        {
            "enabled": true
        }

    Error Responses:
        400 Bad Request
        {
            "error": "Invalid course_key."
        }
    """

    # Emptied so the view itself never reads the session: the answer is the same
    # for every learner, and a 401 from an expired cookie would read as "off".
    authentication_classes = []
    permission_classes = [AllowAny]
    # A 429 is indistinguishable from "off" to a fail-closed client, so throttling
    # this endpoint would turn a rate limit into a feature outage.
    throttle_classes = []

    @method_decorator(cache_control(public=True, max_age=60))
    def get(self, request, course_key_string=None):  # noqa: ARG002
        """
        Resolve the Contact us waffle flag, optionally for a course.
        """
        course_key = None
        if course_key_string:
            try:
                course_key = CourseKey.from_string(course_key_string)
            except InvalidKeyError:
                return Response(
                    {"error": "Invalid course_key."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        enabled = get_contact_us_enabled_flag().is_enabled(course_key)
        return Response({"enabled": enabled})
