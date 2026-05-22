"""App configuration for ol-openedx-uai-content-customization plugin."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenEdxUaiContentCustomizationConfig(AppConfig):
    """App configuration for the ol-openedx-uai-content-customization plugin."""

    name = "ol_openedx_uai_content_customization"
    verbose_name = "OL Open edX UAI Content Customization"

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
