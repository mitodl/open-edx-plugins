# noqa: INP001

"""LMS-only production settings to provide to edX"""

from ol_openedx_course_translations.settings.filters import (
    register_translate_content_filter,
)
from ol_openedx_course_translations.settings.production import (
    plugin_settings as shared_production_settings,
)


def plugin_settings(settings):
    """
    Populate LMS production settings.

    The filter is LMS-only so Studio previews keep showing the source content.
    """
    shared_production_settings(settings)
    register_translate_content_filter(settings)
