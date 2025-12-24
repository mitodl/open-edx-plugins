"""
Middleware to set/reset language preference cookie and
user preference based on course language.
"""

import re

from django.conf import settings
from django.http import HttpResponseRedirect
from django.utils.deprecation import MiddlewareMixin
from opaque_keys.edx.keys import CourseKey
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx.core.djangoapps.lang_pref import LANGUAGE_KEY
from openedx.core.djangoapps.lang_pref import helpers as lang_pref_helpers
from openedx.core.djangoapps.user_api.preferences.api import set_user_preference

ENGLISH_LANGUAGE_CODE = "en"


def should_process_request(request):
    """
    Return True if language auto-selection should run for this request.
    """
    return (
        settings.ENABLE_AUTO_LANGUAGE_SELECTION
        and hasattr(request, "user")
        and request.user.is_authenticated
    )


def set_language(request, response, language):
    """
    Set both cookie and user preference for language.
    """
    lang_pref_helpers.set_language_cookie(request, response, language)
    set_user_preference(request.user, LANGUAGE_KEY, language)


def redirect_current_path(request):
    """
    Redirect to the same URL to ensure language change takes effect.
    """
    return HttpResponseRedirect(request.get_full_path())


class CourseLanguageCookieMiddleware(MiddlewareMixin):
    """
    LMS middleware that:
    - Sets language based on course language
    - Forces English for exempt paths and authoring MFEs
    """

    COURSE_URL_REGEX = re.compile(
        rf"^/courses/(?P<course_key>{settings.COURSE_KEY_REGEX})(?:/|$)",
        re.IGNORECASE,
    )

    def process_response(self, request, response):
        """
        Process the response to set/reset language cookie based on course language.
        """
        if not should_process_request(request):
            return response

        path = getattr(request, "path_info", request.path)

        if self._should_force_english(request, path):
            return self._force_english_if_needed(request, response)

        course_language = self._get_course_language(path)
        if not course_language:
            return response

        return self._apply_course_language(request, response, course_language)

    def _should_force_english(self, request, path):
        """
        Determine if English should be forced based on request origin or exempt paths.
        """
        return request.META.get(
            "HTTP_ORIGIN"
        ) == settings.COURSE_AUTHORING_MICROFRONTEND_URL or any(
            exempt_path in path
            for exempt_path in settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS
        )

    def _force_english_if_needed(self, request, response):
        """
        Force language to English if not already set.
        """
        cookie_val = lang_pref_helpers.get_language_cookie(request)

        if cookie_val != ENGLISH_LANGUAGE_CODE:
            set_language(request, response, ENGLISH_LANGUAGE_CODE)
            return redirect_current_path(request)

        return response

    def _get_course_language(self, path):
        """
        Extract course language from the course URL path.
        """
        match = self.COURSE_URL_REGEX.match(path)
        if not match:
            return None

        try:
            course_key = CourseKey.from_string(match.group("course_key"))
            overview = CourseOverview.get_from_id(course_key)
        except Exception:  # noqa: BLE001
            return None

        return getattr(overview, "language", None)

    def _apply_course_language(self, request, response, language):
        """
        Apply the course language if it differs from the current cookie value.
        """
        cookie_val = lang_pref_helpers.get_language_cookie(request)
        if cookie_val != language:
            set_language(request, response, language)
            return redirect_current_path(request)

        return response


class CourseLanguageCookieResetMiddleware(MiddlewareMixin):
    """
    CMS middleware that always resets language to English.
    """

    def process_response(self, request, response):
        """
        Process the response to reset language cookie to English.
        """
        if not should_process_request(request):
            return response

        cookie_val = lang_pref_helpers.get_language_cookie(request)
        if cookie_val and cookie_val != ENGLISH_LANGUAGE_CODE:
            set_language(request, response, ENGLISH_LANGUAGE_CODE)

        return response
