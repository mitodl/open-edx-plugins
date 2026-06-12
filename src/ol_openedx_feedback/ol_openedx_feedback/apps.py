"""ol_openedx_feedback Django application initialization."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedxFeedbackConfig(AppConfig):
    """Configuration for the ol_openedx_feedback Django application."""

    name = "ol_openedx_feedback"
    verbose_name = "Open edX Block Feedback"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "ol_openedx_feedback",
                PluginURLs.REGEX: "^api/feedback/v1/",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
