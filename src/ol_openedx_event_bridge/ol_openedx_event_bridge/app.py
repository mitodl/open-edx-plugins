"""
Ol Openedx event bridge App Configuration
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSignals
from openedx.core.djangoapps.plugins.constants import ProjectType


class OLEventBridgeConfig(AppConfig):
    """
    Configuration class for Ol Openedx event bridge
    """

    name = "ol_openedx_event_bridge"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.LMS: {
                PluginSignals.RELATIVE_PATH: "receivers",
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_passing_grade",
                        PluginSignals.SIGNAL_PATH: "openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_event_bridge.receivers.listen_for_passing_grade",  # noqa: E501
                    }
                ],
            }
        },
    }
