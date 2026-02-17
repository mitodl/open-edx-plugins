"""
App configuration for ol-openedx-course-sync plugin
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginSignals
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenEdxCourseSyncConfig(AppConfig):
    """
    App configuration for the ol-openedx-course-sync app.
    """

    name = "ol_openedx_course_sync"
    verbose_name = "Open edX Course Sync"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.CMS: {
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_course_publish",
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.COURSE_PUBLISHED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_course_sync.signals.listen_for_course_publish",  # noqa: E501
                    }
                ],
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
