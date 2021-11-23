"""
Canvas Integration Application Configuration
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginURLs

from openedx.core.constants import COURSE_ID_PATTERN
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class CanvasIntegrationConfig(AppConfig):
    """
    Configuration class for Canvas integration app
    """
    name = 'ol_openedx_canvas_integration'

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: '',
                PluginURLs.REGEX: 'courses/{}/canvas/api/'.format(COURSE_ID_PATTERN),
                PluginURLs.RELATIVE_PATH: 'urls',
            }
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.PRODUCTION: {PluginSettings.RELATIVE_PATH: 'settings.production'},
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: 'settings.common'},
            }
        }
    }
