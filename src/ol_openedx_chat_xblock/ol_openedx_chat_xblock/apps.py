"""
ol_openedx_chat_xblock Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedxChatXBlockConfig(AppConfig):
    """
    Configuration for the ol_openedx_chat_xblock Django application.
    """

    name = "ol_openedx_chat_xblock"

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
