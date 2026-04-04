"""
ol_openedx_ai_static_translations Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedXAIStaticTranslationsConfig(AppConfig):
    """
    Configuration for the ol_openedx_ai_static_translations Django application.
    """

    name = "ol_openedx_ai_static_translations"
    verbose_name = "OL AI Static Translations"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.cms"},
            },
        },
    }
