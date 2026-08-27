"""Common settings unique to the canvas integration plugin."""


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""  # noqa: D401
    settings.CANVAS_ACCESS_TOKEN = None
    settings.CANVAS_BASE_URL = None
    settings.CANVAS_COURSE_ID_CACHE_TIMEOUT = 300
