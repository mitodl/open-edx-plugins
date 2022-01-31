"""
ol_openedx_rapid_response_reports Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginContexts, PluginURLs
from openedx.core.constants import COURSE_ID_PATTERN
from openedx.core.djangoapps.plugins.constants import ProjectType

from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_PLUGIN_VIEW_NAME


class RapidResponsePluginConfig(AppConfig):
    """
    Configuration for the ol_openedx_rapid_response_reports Django application.
    """

    name = "ol_openedx_rapid_response_reports"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: f"courses/{COURSE_ID_PATTERN}/instructor/api/",
                PluginURLs.RELATIVE_PATH: "urls",
            }
        },
        PluginContexts.CONFIG: {
            ProjectType.LMS: {
                RAPID_RESPONSE_PLUGIN_VIEW_NAME: "ol_openedx_rapid_response_reports.context_api.plugin_context"
            }
        },
    }
