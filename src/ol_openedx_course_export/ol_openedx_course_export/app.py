"""
Course Export Application Configuration
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class CourseExportConfig(AppConfig):
    """
    Configuration class for course export app
    """

    name = "ol_openedx_course_export"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.CMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: "^api/courses/v0/export/",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            }
        },
    }
