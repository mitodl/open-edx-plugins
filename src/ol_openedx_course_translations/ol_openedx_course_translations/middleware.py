# python
import re

from django.utils.deprecation import MiddlewareMixin
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference


class CourseLanguageCookieMiddleware(MiddlewareMixin):
    """
    Sets language preference cookie and user preference based on course language.
    """

    COURSE_URL_REGEX = re.compile(
        r"^/courses/(?P<course_key>course-v1:[A-Za-z0-9._-]+(?:\+[A-Za-z0-9._-]+)+)(?:/|$)",
        re.IGNORECASE,
    )
    COOKIE_NAME = "openedx-language-preference"

    def process_response(self, request, response):
        path = getattr(request, "path_info", request.path)
        match = self.COURSE_URL_REGEX.match(path)
        if not match:
            return response

        course_key_str = match.group("course_key")
        try:
            course_key = CourseKey.from_string(course_key_str)
            overview = CourseOverview.get_from_id(course_key)
        except Exception:  # noqa: BLE001
            return response

        language = getattr(overview, "language", None)
        response.set_cookie(
            self.COOKIE_NAME,
            language or "",
            max_age=60 * 60 * 24 * 180,
            httponly=False,
            samesite="Lax",
        )

        # Set user preference if authenticated
        if language and hasattr(request, "user") and request.user.is_authenticated:
            set_user_preference(request.user, LANGUAGE_KEY, language)

        return response
