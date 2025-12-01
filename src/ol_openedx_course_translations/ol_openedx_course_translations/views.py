"""
API Views for ol_openedx_course_translations App
"""

from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView


class CourseLanguageView(APIView):
    """
    API View to retrieve the language of a specified course.
    """

    def get(self, request, course_key_string):  # noqa: ARG002
        try:
            course_key = CourseKey.from_string(course_key_string)
            course = CourseOverview.get_from_id(course_key)
        except Exception:  # noqa: BLE001
            return Response(
                {"error": "Invalid course_key or course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response({"language": course.language})
