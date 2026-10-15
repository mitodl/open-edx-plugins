# noqa: INP001

"""Settings to provide to edX"""

from ol_openedx_course_translations.settings.common import apply_common_settings
from ol_openedx_course_translations.settings.filters import (
    register_translate_content_filter,
)


def plugin_settings(settings):
    """
    Populate lms settings
    """
    apply_common_settings(settings)
    register_translate_content_filter(settings)
