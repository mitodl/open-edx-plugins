"""
Settings for mitxpro-core
"""

SECRET_KEY = "unsafe-secret-key"  # noqa: S105  # pragma: allowlist secret
INSTALLED_APPS = (
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
)


def plugin_settings(settings):
    """Apply default settings for this plugin"""
    settings.MITXPRO_CORE_REDIRECT_ENABLED = True
    settings.MITXPRO_CORE_REDIRECT_LOGIN_URL = (
        "/auth/login/mitxpro-oauth2/?auth_entry=login"
    )
    settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST = [
        r"^/(admin|auth|login|logout|register|api|oauth2|user_api)"
    ]
    settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST = []

    settings.MIDDLEWARE.extend(
        ["openedx_companion_auth.middleware.RedirectAnonymousUsersToLoginMiddleware"]
    )
