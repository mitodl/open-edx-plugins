"""Settings to provide to edX"""

from ol_openedx_ai_static_translations.settings import apply_common_settings


def plugin_settings(settings):
    """
    Populate cms settings
    """
    apply_common_settings(settings)
