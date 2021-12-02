"""
ol_openedx_rapid_response_reports Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginURLs, PluginContexts

from openedx.core.constants import COURSE_ID_PATTERN
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType
from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_PLUGIN_VIEW_NAME


class RapidResponsePluginConfig(AppConfig):
    """
    Configuration for the ol_openedx_rapid_response_reports Django application.
    """

    name = 'ol_openedx_rapid_response_reports'

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: '',
                PluginURLs.REGEX: 'courses/{}/instructor/api/'.format(COURSE_ID_PATTERN),
                PluginURLs.RELATIVE_PATH: 'urls',
            }
        },
        PluginContexts.CONFIG: {
            ProjectType.LMS: {
                RAPID_RESPONSE_PLUGIN_VIEW_NAME: 'ol_openedx_rapid_response_reports.context_api.plugin_context'
            }
        }
    }
