# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_auto_select_language.settings.common import apply_common_settings
from ol_openedx_auto_select_language.settings.filters import (
    register_video_language_filter,
)


def plugin_settings(settings):
    """
    Populate lms settings
    """
    apply_common_settings(settings)
    settings.MIDDLEWARE.extend(
        ["ol_openedx_auto_select_language.middleware.CourseLanguageCookieMiddleware"]
    )
    # Register the video-language render filter (adds to any existing pipeline).
    register_video_language_filter(settings)
