"""
Production settings for openedx-companion-auth
"""


def plugin_settings(settings):
    """Apply production settings for this plugin"""
    settings.MITX_REDIRECT_ENABLED = getattr(settings, "ENV_TOKENS", {}).get(
        "MITX_REDIRECT_ENABLED", settings.MITX_REDIRECT_ENABLED
    )

    settings.MITX_REDIRECT_LOGIN_URL = getattr(settings, "ENV_TOKENS", {}).get(
        "MITX_REDIRECT_LOGIN_URL", settings.MITX_REDIRECT_LOGIN_URL
    )

    settings.MITX_REDIRECT_ALLOW_RE_LIST = getattr(settings, "ENV_TOKENS", {}).get(
        "MITX_REDIRECT_ALLOW_RE_LIST",
        settings.MITX_REDIRECT_ALLOW_RE_LIST,
    )

    settings.MITX_REDIRECT_DENY_RE_LIST = getattr(settings, "ENV_TOKENS", {}).get(
        "MITX_REDIRECT_DENY_RE_LIST",
        settings.MITX_REDIRECT_DENY_RE_LIST,
    )
