"""AppConfig for rapid response"""
from django.apps import AppConfig
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType
from edx_django_utils.plugins import PluginSettings, PluginURLs


class RapidResponseAppConfig(AppConfig):
    """
    AppConfig for rapid response
    """
    name = "rapid_response_xblock"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: 'settings.settings'
                },
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: 'settings.cms_settings'
                },
            }
        },
        PluginURLs.CONFIG: {
            ProjectType.CMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: "^toggle-rapid-response/",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
    }
