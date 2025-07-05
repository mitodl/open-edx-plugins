"""
Canvas Integration Application Configuration
"""

from django.apps import AppConfig
from edx_django_utils.plugins import (
    PluginContexts,
    PluginSettings,
    PluginSignals,
    PluginURLs,
)
from lms.djangoapps.instructor.constants import INSTRUCTOR_DASHBOARD_PLUGIN_VIEW_NAME
from openedx.core.constants import COURSE_ID_PATTERN
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class CanvasIntegrationConfig(AppConfig):
    """
    Configuration class for Canvas integration app
    """

    name = "ol_openedx_canvas_integration"

    plugin_app = {
        PluginURLs.CONFIG: {
            ProjectType.LMS: {
                PluginURLs.NAMESPACE: "",
                PluginURLs.REGEX: f"courses/{COURSE_ID_PATTERN}/canvas/api/",
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
        PluginContexts.CONFIG: {
            ProjectType.LMS: {
                INSTRUCTOR_DASHBOARD_PLUGIN_VIEW_NAME: "ol_openedx_canvas_integration.context_api.plugin_context"  # noqa: E501
            }
        },
        PluginSignals.CONFIG: {
            ProjectType.LMS: {
                PluginSignals.RELATIVE_PATH: "receivers",
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "update_grade_in_canvas",
                        PluginSignals.SIGNAL_PATH: "django.db.models.signals.post_save",
                        PluginSignals.SENDER_PATH: "lms.djangoapps.grades.models.PersistentSubsectionGrade",  # noqa: E501
                    }
                ],
            }
        },
    }

    def ready(self):
        """Perform initialization tasks required for the plugin."""
        from ol_openedx_canvas_integration import handlers  # noqa: F401, PLC0415
