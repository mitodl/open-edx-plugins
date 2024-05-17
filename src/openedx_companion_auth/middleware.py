"""MIT xPro Open edX middlware"""
import re

from django.conf import settings
from django.shortcuts import redirect
from django.utils.deprecation import MiddlewareMixin


try:
    from urllib.parse import urlsplit, urlunsplit, parse_qsl
except ImportError:
    from urlparse import urlsplit, urlunsplit, parse_qsl

try:
    from django.utils.http import urlquote
except ImportError:
    from urllib.parse import quote as urlquote  # pylint: disable=ungrouped-imports


def redirect_to_login(request):
    """Returns a response redirecting to the login url"""
    scheme, netloc, path, query, fragment = urlsplit(
        settings.MITXPRO_CORE_REDIRECT_LOGIN_URL
    )
    query = parse_qsl(query)
    query.append(("next", urlquote(request.build_absolute_uri())))
    query = "&".join(
        [
            "{}={}".format(key, value)  # pylint: disable=consider-using-f-string
            for (key, value) in query
        ]
    )
    return redirect(urlunsplit((scheme, netloc, path, query, fragment)))


class RedirectAnonymousUsersToLoginMiddleware(MiddlewareMixin):
    """Middleware to redirect anonymous users to login via xpro"""

    def process_request(self, request):
        """Process an incoming request"""
        if settings.MITXPRO_CORE_REDIRECT_ENABLED and (
            not getattr(request, "user", None) or request.user.is_anonymous
        ):
            # if allowed regexes are set, redirect if the path doesn't match any
            allowed_regexes = settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST
            if allowed_regexes and not any(  # pylint: disable=use-a-generator
                [re.match(pattern, request.path) for pattern in allowed_regexes]
            ):
                return redirect_to_login(request)

            # if denied regexes are set, redirect if the path matches any
            denied_regexes = settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST
            if denied_regexes and any(  # pylint: disable=use-a-generator
                [re.match(pattern, request.path) for pattern in denied_regexes]
            ):
                return redirect_to_login(request)

        return None
