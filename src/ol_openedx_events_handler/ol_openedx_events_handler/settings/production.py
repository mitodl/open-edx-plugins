"""Production plugin settings for the OL Open edX events handler plugin."""


def plugin_settings(settings):
    """
    Production settings — reads values from environment/auth tokens.
    """
    env_tokens = getattr(settings, "ENV_TOKENS", {})

    settings.ENROLLMENT_WEBHOOK_URL = env_tokens.get(
        "ENROLLMENT_WEBHOOK_URL", settings.ENROLLMENT_WEBHOOK_URL
    )
    settings.ENROLLMENT_WEBHOOK_KEY = env_tokens.get(
        "ENROLLMENT_WEBHOOK_KEY", settings.ENROLLMENT_WEBHOOK_KEY
    )
    settings.ENROLLMENT_COURSE_ACCESS_ROLES = env_tokens.get(
        "ENROLLMENT_COURSE_ACCESS_ROLES", settings.ENROLLMENT_COURSE_ACCESS_ROLES
    )
