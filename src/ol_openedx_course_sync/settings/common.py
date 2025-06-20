"""Common settings unique to the course sync plugin."""


def plugin_settings(settings):
    """Settings for the course sync plugin."""  # noqa: D401
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME = env_tokens.get(
        "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME", ""
    )
