"""Production settings for the ol-openedx-short-video-course plugin."""

from ol_openedx_short_video_course.settings.common import (
    plugin_settings as _common_plugin_settings,
)


def plugin_settings(settings):
    """Apply production-time plugin settings."""
    _common_plugin_settings(settings)
