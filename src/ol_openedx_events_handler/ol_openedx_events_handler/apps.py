"""Django app configuration for the OL Open edX events handler plugin."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginSignals
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType

_COURSE_ACCESS_ROLE_ADDED_RECEIVER = {
    PluginSignals.RECEIVER_FUNC_NAME: "handle_course_access_role_added",
    PluginSignals.SIGNAL_PATH: (
        "openedx_events.learning.signals.COURSE_ACCESS_ROLE_ADDED"
    ),
    PluginSignals.DISPATCH_UID: (
        "ol_openedx_events_handler.handlers.course_access_role"
        ".handle_course_access_role_added"
    ),
}


class OlOpenedxEventsHandlerConfig(AppConfig):
    """App configuration for the OL Open edX events handler plugin."""

    name = "ol_openedx_events_handler"
    verbose_name = "OL Open edX Events Handler"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.LMS: {
                PluginSignals.RELATIVE_PATH: "handlers.course_access_role",
                PluginSignals.RECEIVERS: [_COURSE_ACCESS_ROLE_ADDED_RECEIVER],
            },
            ProjectType.CMS: {
                PluginSignals.RELATIVE_PATH: "handlers.course_access_role",
                PluginSignals.RECEIVERS: [_COURSE_ACCESS_ROLE_ADDED_RECEIVER],
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                },
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production",
                },
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                },
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production",
                },
            },
        },
    }
