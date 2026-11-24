"""App configuration for the ol-openedx-video-thumbnail-copy plugin."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenEdxVideoThumbnailCopyConfig(AppConfig):
    """App configuration for the ol-openedx-video-thumbnail-copy plugin."""

    name = "ol_openedx_video_thumbnail_copy"
    verbose_name = "OL Open edX Video Thumbnail Copy"

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
