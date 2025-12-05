"""
API Views for ol_openedx_course_translations App
"""

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


class CourseLanguageView(APIView):
    """
    API View to retrieve the language of a specified course.
    """

    def get(self, request, course_key_string):  # noqa: ARG002
        if not course_key_string:
            return Response(
                {"error": "Missing course_key parameter."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            course_key = CourseKey.from_string(course_key_string)
            course = CourseOverview.get_from_id(course_key)
        except Exception:  # noqa: BLE001
            return Response(
                {"error": "Invalid course_key or course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"language": course.language})


class ResetUserLanguageView(APIView):
    """
    API endpoint to reset user's language preference and cookie to English.
    """

    permission_classes = [IsAuthenticated]
    COOKIE_NAME = "openedx-language-preference"

    def post(self, request):
        # Set user preference
        set_user_preference(request.user, LANGUAGE_KEY, "en")

        # Prepare response
        response = Response(
            {"detail": "Language reset to English."}, status=status.HTTP_200_OK
        )

        # Set cookie like middleware
        response.set_cookie(
            self.COOKIE_NAME,
            "en",
            max_age=60 * 60 * 24 * 180,
            httponly=False,
            samesite="Lax",
        )

        return response
