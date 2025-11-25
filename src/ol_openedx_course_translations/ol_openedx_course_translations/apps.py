"""
ol_openedx_course_translations Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedXCourseTranslationsConfig(AppConfig):
    """
    Configuration for the ol_openedx_course_translations Django application.
    """

    name = "ol_openedx_course_translations"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
