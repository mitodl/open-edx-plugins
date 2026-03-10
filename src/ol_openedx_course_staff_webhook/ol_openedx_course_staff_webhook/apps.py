"""Django app configuration for the course staff webhook plugin."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginSignals

_RECEIVER_FUNC = "listen_for_course_access_role_added"
_SIGNAL_PATH = (
    "openedx_events.learning.signals.COURSE_ACCESS_ROLE_ADDED"
)
_DISPATCH_UID = (
    "ol_openedx_course_staff_webhook"
    ".signals.listen_for_course_access_role_added"
)

_SIGNAL_RECEIVER = {
    PluginSignals.RECEIVER_FUNC_NAME: _RECEIVER_FUNC,
    PluginSignals.SIGNAL_PATH: _SIGNAL_PATH,
    PluginSignals.DISPATCH_UID: _DISPATCH_UID,
}


class CourseStaffWebhookConfig(AppConfig):
    """App configuration for the course staff webhook plugin."""

    name = "ol_openedx_course_staff_webhook"
    verbose_name = "Course Staff Webhook"

    plugin_app = {
        PluginSignals.CONFIG: {
            "lms.djangoapp": {
                PluginSignals.RELATIVE_PATH: "signals",
                PluginSignals.RECEIVERS: [_SIGNAL_RECEIVER],
            },
            "cms.djangoapp": {
                PluginSignals.RELATIVE_PATH: "signals",
                PluginSignals.RECEIVERS: [_SIGNAL_RECEIVER],
            },
        },
        PluginSettings.CONFIG: {
            "lms.djangoapp": {
                "common": {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                },
                "production": {
                    PluginSettings.RELATIVE_PATH: "settings.production",
                },
            },
            "cms.djangoapp": {
                "common": {
                    PluginSettings.RELATIVE_PATH: "settings.common",
                },
                "production": {
                    PluginSettings.RELATIVE_PATH: "settings.production",
                },
            },
        },
    }
