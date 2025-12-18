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


class CourseLanguageCookieMiddleware(MiddlewareMixin):
    """
    Sets language preference cookie and user preference based on course language.
    Also ensures that for admin URLs, the language is always set to 'en'.
    """

    COURSE_URL_REGEX = re.compile(
        rf"^/courses/(?P<course_key>{settings.COURSE_KEY_REGEX})(?:/|$)",
        re.IGNORECASE,
    )

    def process_response(self, request, response):  # noqa: PLR0911
        """
        Set language preference cookie and user preference based on course language.
        """
        if (
            not hasattr(request, "user")
            or not request.user.is_authenticated
            or not settings.ENABLE_AUTO_LANGUAGE_SELECTION
        ):
            return response

        path = getattr(request, "path_info", request.path)

        # Force language to English for exempt paths and certain origins
        if request.META.get(
            "HTTP_ORIGIN"
        ) == settings.COURSE_AUTHORING_MICROFRONTEND_URL or any(
            exempt_path in path
            for exempt_path in settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS
        ):
            cookie_val = lang_pref_helpers.get_language_cookie(request)
            needs_lang_reset = not cookie_val or cookie_val != ENGLISH_LANGUAGE_CODE
            if needs_lang_reset:
                lang_pref_helpers.set_language_cookie(
                    request, response, ENGLISH_LANGUAGE_CODE
                )
                if hasattr(request, "user") and request.user.is_authenticated:
                    set_user_preference(
                        request.user, LANGUAGE_KEY, ENGLISH_LANGUAGE_CODE
                    )
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
        if not language:
            return response

        lang_pref_helpers.set_language_cookie(request, response, language)
        set_user_preference(request.user, LANGUAGE_KEY, language)

        # Redirect if cookie is not present or is different from the desired language
        cookie_val = lang_pref_helpers.get_language_cookie(request)
        if cookie_val != language:
            url = request.get_full_path()
            return HttpResponseRedirect(url)

        return response


class CourseLanguageCookieResetMiddleware(MiddlewareMixin):
    """
    Resets language preference cookie and user preference to English
    for Studio/CMS URLs.
    """

    def process_response(self, request, response):
        """
        Reset language preference cookie and user preference to
        English for Studio/CMS URLs.
        """
        if (
            not hasattr(request, "user")
            or not request.user.is_authenticated
            or not settings.ENABLE_AUTO_LANGUAGE_SELECTION
        ):
            return response

        cookie_val = lang_pref_helpers.get_language_cookie(request)
        if cookie_val and cookie_val != ENGLISH_LANGUAGE_CODE:
            lang_pref_helpers.set_language_cookie(
                request, response, ENGLISH_LANGUAGE_CODE
            )
            set_user_preference(request.user, LANGUAGE_KEY, ENGLISH_LANGUAGE_CODE)
        return response
