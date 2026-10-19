# noqa: INP001

"""Production settings to provide to edX"""

from ol_openedx_course_translations.settings.common import (
    apply_azure_openai_settings,
)


def plugin_settings(settings):
    """
    Populate production settings for LMS and CMS.

    Common plugin settings run before production.py loads the YAML config, so
    AZURE_OPENAI_* and the deployed TRANSLATIONS_PROVIDERS are only visible
    from here. This must not call apply_common_settings, which would replace
    the deployed TRANSLATIONS_PROVIDERS with the empty defaults.
    """
    apply_azure_openai_settings(settings)
