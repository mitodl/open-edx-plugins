"""
API Views for ol_openedx_auto_select_language App
"""

import logging

from django.conf import settings
from django.utils.translation import get_language
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers
from openedx.core.djangoapps.lang_pref.api import released_languages
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from ol_openedx_auto_select_language.toggles import in_place_translations_enabled
from ol_openedx_auto_select_language.translations import course_language_codes
from ol_openedx_auto_select_language.utils import LanguageCode

log = logging.getLogger(__name__)


class CourseLanguageAnonRateThrottle(AnonRateThrottle):
    """Throttle anonymous requests for course language endpoint."""

    scope = "course_language_anon"
    rate = settings.COURSE_LANGUAGE_ANON_THROTTLE_RATE


class CourseLanguageUserRateThrottle(UserRateThrottle):
    """Throttle authenticated requests for course language endpoint."""

    scope = "course_language_user"
    rate = settings.COURSE_LANGUAGE_USER_THROTTLE_RATE


class CourseLanguageView(APIView):
    """
    API View to retrieve the language of a specified course.

    Sample Request:
        GET /auto-select-language/api/course_language/{course_key}/

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

    permission_classes = [AllowAny]
    throttle_classes = [CourseLanguageAnonRateThrottle, CourseLanguageUserRateThrottle]

    def get(self, request, course_key_string):
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
        if in_place_translations_enabled(course_key):
            # The MIT Footer switches the site to this language whenever it
            # differs from the cookie, so echoing the cookie keeps the
            # learner's own choice.
            language = lang_pref_helpers.get_language_cookie(request) or get_language()
        else:
            language = LanguageCode(course.language).to_bcp47()
        return Response({"language": language})


class ReleasedLanguagesView(APIView):
    """
    API View for the header language dropdown.

    ``enabled`` mirrors the in-place translations flag for ``course_id`` (or its
    global value without one), so frontends show the dropdown and stop forcing
    a language only when the flag is on. With a ``course_id``, ``languages`` is
    limited to the course's own language, the languages it has translations
    for, and the learner's current language (so the dropdown can show it).

    Sample Request:
        GET /auto-select-language/api/languages/?course_id={course_key}

    Sample Response:
        200 OK
        {
            "enabled": true,
            "languages": [
                {"code": "en", "name": "English"},
                {"code": "fr", "name": "Français"}
            ]
        }
    """

    permission_classes = [AllowAny]
    throttle_classes = [CourseLanguageAnonRateThrottle, CourseLanguageUserRateThrottle]

    def get(self, request):
        """Return the flag state and the DarkLang released languages."""
        try:
            course_key = CourseKey.from_string(request.GET["course_id"])
        except (KeyError, InvalidKeyError):
            course_key = None
        languages = released_languages()
        if course_key:
            codes = course_language_codes(course_key) | {get_language()}
            languages = [language for language in languages if language.code in codes]
        return Response(
            {
                "enabled": in_place_translations_enabled(course_key),
                "languages": [
                    {"code": language.code, "name": language.name}
                    for language in languages
                ],
            }
        )
