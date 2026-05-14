"""App configuration for the ol-openedx-short-video-course plugin."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenEdxShortVideoCourseConfig(AppConfig):
    """App configuration for ol-openedx-short-video-course."""

    name = "ol_openedx_short_video_course"
    verbose_name = "Open edX Short Video Course"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
