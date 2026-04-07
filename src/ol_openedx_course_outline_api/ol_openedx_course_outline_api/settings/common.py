"""Common settings unique to the course outline API plugin."""


def plugin_settings(settings):
    """Settings for the course outline API plugin."""  # noqa: D401
    settings.OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX = getattr(
        settings,
        "OL_COURSE_OUTLINE_API_CACHE_KEY_PREFIX",
        "ol_course_outline_api:outline:v0:",
    )
    settings.OL_COURSE_OUTLINE_API_CACHE_TIMEOUT_SECONDS = getattr(
        settings,
        "OL_COURSE_OUTLINE_API_CACHE_TIMEOUT_SECONDS",
        60 * 60 * 24 * 7,
    )
