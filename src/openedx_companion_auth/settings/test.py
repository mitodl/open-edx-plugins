"""
Settings for mitxpro_core-core
"""

from __future__ import absolute_import, unicode_literals

from .common import *  # pylint: disable=wildcard-import, unused-wildcard-import


class SettingsClass(object):  # pylint: disable=useless-object-inheritance
    """ dummy settings class """


def plugin_settings(settings):  # pylint: disable=function-redefined
    """
    Configure the plugin for tests
    """
    settings.MITXPRO_CORE_REDIRECT_ENABLED = True
    settings.MITXPRO_CORE_REDIRECT_LOGIN_URL = (
        "/auth/login/mitxpro-oauth2/?auth_entry=login"
    )
    settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST = [
        r"^/(admin|auth|login|logout|register|api|oauth2|user_api)"
    ]
    settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST = []

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
