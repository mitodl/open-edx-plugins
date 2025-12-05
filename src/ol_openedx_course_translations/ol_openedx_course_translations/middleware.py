# python
import re

from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference

from django.conf import settings


class CourseLanguageCookieMiddleware(MiddlewareMixin):
    """
    Sets language preference cookie and user preference based on course language.
    Also ensures that for admin URLs, the language is always set to 'en'.
    """

    COURSE_URL_REGEX = re.compile(
        rf"^/courses/(?P<course_key>{settings.COURSE_KEY_REGEX})(?:/|$)",
        re.IGNORECASE,
    )
    COOKIE_NAME = "openedx-language-preference"

    def process_response(self, request, response):
        path = getattr(request, "path_info", request.path)

        # Force 'en' language for admin, sysadmin, and instructor dashboard URLs
        if path.startswith("/admin") or path.startswith("/sysadmin") or "instructor" in path:
            cookie_val = request.COOKIES.get(self.COOKIE_NAME)
            needs_reload = cookie_val and cookie_val != "en"
            if needs_reload:
                response.set_cookie(
                    self.COOKIE_NAME,
                    "en",
                    max_age=60 * 60 * 24 * 180,
                    httponly=False,
                    samesite="Lax",
                )
                if hasattr(request, "user") and request.user.is_authenticated:
                    set_user_preference(request.user, LANGUAGE_KEY, "en")
                return HttpResponseRedirect(request.get_full_path())
            return response

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

        # Redirect if cookie is not present or is different from the desired language
        cookie_val = request.COOKIES.get(self.COOKIE_NAME)
        needs_reload = language and (cookie_val != language)
        if needs_reload:
            url = request.get_full_path()
            return HttpResponseRedirect(url)

        return response
