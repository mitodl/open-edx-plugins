"""Production plugin settings for the course staff webhook plugin."""


def plugin_settings(settings):
    """
    Production settings — reads values from environment/auth tokens.
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    settings.MITXONLINE_WEBHOOK_URL = env_tokens.get(
        "MITXONLINE_WEBHOOK_URL", settings.MITXONLINE_WEBHOOK_URL
    )
    settings.MITXONLINE_WEBHOOK_KEY = env_tokens.get(
        "MITXONLINE_WEBHOOK_KEY", settings.MITXONLINE_WEBHOOK_KEY
    )
    settings.MITXONLINE_COURSE_STAFF_ROLES = env_tokens.get(
        "MITXONLINE_COURSE_STAFF_ROLES", settings.MITXONLINE_COURSE_STAFF_ROLES
    )
