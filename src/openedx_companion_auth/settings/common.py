"""
Settings for openedx-companion-auth
"""


def plugin_settings(settings):
    """Apply default settings for this plugin"""
    settings.MITX_REDIRECT_ENABLED = True
    settings.MITX_REDIRECT_LOGIN_URL = "/auth/login/ol-oauth2/?auth_entry=login"
    settings.MITX_REDIRECT_ALLOW_RE_LIST = [
        r"^/(admin|auth|login|logout|register|api|oauth2|user_api)"
    ]
    settings.MITX_REDIRECT_DENY_RE_LIST = []

    settings.MIDDLEWARE.extend(
        ["openedx_companion_auth.middleware.RedirectAnonymousUsersToLoginMiddleware"]
    )
