"""
ol_openedx_chat Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedxChatConfig(AppConfig):
    """
    Configuration for the ol_openedx_chat Django application.
    """

    name = "ol_openedx_chat"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
                SettingsType.DEVSTACK: {
                    PluginSettings.RELATIVE_PATH: "settings.devstack"
                },
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
                SettingsType.DEVSTACK: {
                    PluginSettings.RELATIVE_PATH: "settings.devstack"
                },
            },
        },
    }
