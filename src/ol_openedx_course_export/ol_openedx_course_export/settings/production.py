"""Production settings unique to the course export plugin."""


def plugin_settings(settings):
    """Settings for the course export plugin."""  # noqa: D401
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.COURSE_EXPORT_CELERY_QUEUE = env_tokens.get("COURSE_EXPORT_CELERY_QUEUE")
