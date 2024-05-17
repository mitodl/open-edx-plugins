"""
Production settings for mitxpro-core
"""
from __future__ import unicode_literals


def plugin_settings(settings):
    """Apply production settings for this plugin"""
    settings.MITXPRO_CORE_REDIRECT_ENABLED = getattr(settings, "ENV_TOKENS", {}).get(
        "MITXPRO_CORE_REDIRECT_ENABLED", settings.MITXPRO_CORE_REDIRECT_ENABLED
    )

    settings.MITXPRO_CORE_REDIRECT_LOGIN_URL = getattr(settings, "ENV_TOKENS", {}).get(
        "MITXPRO_CORE_REDIRECT_LOGIN_URL", settings.MITXPRO_CORE_REDIRECT_LOGIN_URL
    )

    settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST = getattr(
        settings, "ENV_TOKENS", {}
    ).get(
        "MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST",
        settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST,
    )

    settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST = getattr(
        settings, "ENV_TOKENS", {}
    ).get(
        "MITXPRO_CORE_REDIRECT_DENY_RE_LIST",
        settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST,
    )
