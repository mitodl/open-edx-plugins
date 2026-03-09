"""
ol_openedx_auto_select_language Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenEdxAutoSelectLanguageConfig(AppConfig):
    """
    Configuration for the ol_openedx_auto_select_language Django application.
    """

    name = "ol_openedx_auto_select_language"
    verbose_name = "OL Auto Select Language"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: "",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.cms"},
            },
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.lms"},
            },
        },
    }
