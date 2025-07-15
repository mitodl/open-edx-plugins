"""
Settings for openedx-companion-auth
"""

from .common import *  # pylint: disable=wildcard-import, unused-wildcard-import  # noqa: F403


class SettingsClass:  # pylint: disable=useless-object-inheritance
    """dummy settings class"""


def plugin_settings(  # type: ignore[no-redef]
    settings,
):  # pylint: disable=function-redefined
    """
    Configure the plugin for tests
    """
    settings.MITX_REDIRECT_ENABLED = True
    settings.MITX_REDIRECT_LOGIN_URL = "/auth/login/ol-oauth2/?auth_entry=login"
    settings.MITX_REDIRECT_ALLOW_RE_LIST = [
        r"^/(admin|auth|login|logout|register|api|oauth2|user_api)"
    ]
    settings.MITX_REDIRECT_DENY_RE_LIST = []

    settings.MIDDLEWARE = [
        "openedx_companion_auth.middleware.RedirectAnonymousUsersToLoginMiddleware"
    ]


SETTINGS = SettingsClass()
plugin_settings(SETTINGS)
vars().update(SETTINGS.__dict__)


ROOT_URLCONF = "openedx_companion_auth.urls"
ALLOWED_HOSTS = ["*"]

# This key needs to be defined so that the check_apps_ready passes and the
# AppRegistry is loaded
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": "db.sqlite3"}}
