"""
This module initializes and configures the Django application with OTel monitoring.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from ol_openedx_otel_monitoring.client import initialize_otel
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OTelMonitoringConfig(AppConfig):
    name = "ol_openedx_otel_monitoring"
    verbose_name = "OTel Integration for OpenEdx"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "otel_health_check",
                PluginURLs.REGEX: "",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }

    def ready(self):
        super().ready()
        initialize_otel()
