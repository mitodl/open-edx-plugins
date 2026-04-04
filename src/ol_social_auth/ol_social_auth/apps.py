"""ol_social_auth Django application initialization."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLSocialAuthConfig(AppConfig):
    name = "ol_social_auth"
    verbose_name = "OL Social Auth"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                },
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production",
                },
            },
        },
    }
