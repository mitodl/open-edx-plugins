"""
API Views for ol_openedx_course_translations App
"""

import logging

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)


class CourseLanguageView(APIView):
    """
    API View to retrieve the language of a specified course.

    Sample Request:
        GET /course-translations/api/course_language/{course_key}/

    Sample Response:
        200 OK
        {
            "language": "en"
        }

    Error Responses:
        400 Bad Request
        {
            "error": "Invalid course_key."
        }
        404 Not Found
        {
            "error": "Course not found."
        }
        400 Bad Request
        {
            "error": "An unexpected error occurred."
        }
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, course_key_string):  # noqa: ARG002
        """
        Retrieve the language of the specified course.
        """
        try:
            course_key = CourseKey.from_string(course_key_string)
            course = CourseOverview.get_from_id(course_key)
        except InvalidKeyError:
            log.info("Invalid course key %s", course_key_string)
            return Response(
                {"error": "Invalid course_key."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except CourseOverview.DoesNotExist:
            log.info("Course not found for key %s", course_key_string)
            return Response(
                {"error": "Course not found."},
                status=status.HTTP_404_NOT_FOUND,
            )
        except Exception:
            log.exception("Unexpected error retrieving course %s", course_key_string)
            return Response(
                {"error": "An unexpected error occurred."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response({"language": course.language})
