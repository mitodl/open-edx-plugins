"""Common settings unique to the canvas integration plugin."""

from ol_openedx_canvas_integration.settings.lms.filters import (
    register_instructor_tab_filter,
)


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""  # noqa: D401
    settings.CANVAS_ACCESS_TOKEN = None
    settings.CANVAS_BASE_URL = None

    # Register the instructor-dashboard tab filter so the "Canvas" tab is only
    # shown for courses linked to Canvas (canvas_id set in advanced settings).
    register_instructor_tab_filter(settings)
