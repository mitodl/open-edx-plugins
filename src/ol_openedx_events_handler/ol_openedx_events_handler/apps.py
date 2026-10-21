"""Django app configuration for the OL Open edX events handler plugin."""

from importlib.util import find_spec

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginSignals
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


def _authz_signals_available():
    """
    Whether openedx-events ships the authz signals this plugin can listen for.

    ``openedx_events.authz`` arrived in openedx-events 11.2.0, so it is absent
    on releases that pin an earlier version (Ulmo is on 10.5.0). Registering a
    receiver for a signal path that cannot be imported is not a soft failure:
    ``connect_plugin_receivers`` resolves every ``SIGNAL_PATH`` with
    ``import_string`` and nothing in that chain catches ImportError, so the
    whole LMS or CMS fails to start. Skipping the receiver where the signal
    does not exist keeps those releases working; they have no openedx-authz to
    emit it in the first place.
    """
    try:
        return find_spec("openedx_events.authz.signals") is not None
    except ModuleNotFoundError:
        # find_spec imports the parent package to look for the submodule, so an
        # absent openedx_events.authz raises here rather than returning None.
        return False


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

_ROLE_ASSIGNMENT_CREATED_RECEIVER = {
    PluginSignals.RECEIVER_FUNC_NAME: "handle_role_assignment_created",
    PluginSignals.SIGNAL_PATH: "openedx_events.authz.signals.ROLE_ASSIGNMENT_CREATED",
    PluginSignals.DISPATCH_UID: (
        "ol_openedx_events_handler.handlers.role_assignment"
        ".handle_role_assignment_created"
    ),
}

_COURSE_ENROLLMENT_CREATED_RECEIVER = {
    PluginSignals.RECEIVER_FUNC_NAME: "handle_course_enrollment_created",
    PluginSignals.SIGNAL_PATH: (
        "openedx_events.learning.signals.COURSE_ENROLLMENT_CREATED"
    ),
    PluginSignals.DISPATCH_UID: (
        "ol_openedx_events_handler.handlers.enrollment.handle_course_enrollment_created"
    ),
}

_COURSE_GRADE_NOW_PASSED_RECEIVER = {
    PluginSignals.RECEIVER_FUNC_NAME: "listen_for_passing_grade",
    PluginSignals.SIGNAL_PATH: (
        "openedx.core.djangoapps.signals.signals.COURSE_GRADE_NOW_PASSED"
    ),
    PluginSignals.DISPATCH_UID: (
        "ol_openedx_events_handler.receivers.certificate_passing_receiver"
        ".listen_for_passing_grade"
    ),
}

_AUTHZ_RECEIVERS = (
    [_ROLE_ASSIGNMENT_CREATED_RECEIVER] if _authz_signals_available() else []
)

_SETTINGS_CONFIG = {
    SettingsType.COMMON: {
        PluginSettings.RELATIVE_PATH: "settings.common",
    },
    SettingsType.PRODUCTION: {
        PluginSettings.RELATIVE_PATH: "settings.production",
    },
}


class OlOpenedxEventsHandlerConfig(AppConfig):
    """App configuration for the OL Open edX events handler plugin."""

    name = "ol_openedx_events_handler"
    verbose_name = "OL Open edX Events Handler"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.LMS: {
                PluginSignals.RELATIVE_PATH: "handlers.lms",
                PluginSignals.RECEIVERS: [
                    _COURSE_ACCESS_ROLE_ADDED_RECEIVER,
                    *_AUTHZ_RECEIVERS,
                    _COURSE_ENROLLMENT_CREATED_RECEIVER,
                    _COURSE_GRADE_NOW_PASSED_RECEIVER,
                ],
            },
            ProjectType.CMS: {
                PluginSignals.RELATIVE_PATH: "handlers.cms",
                PluginSignals.RECEIVERS: [
                    _COURSE_ACCESS_ROLE_ADDED_RECEIVER,
                    *_AUTHZ_RECEIVERS,
                ],
            },
        },
        PluginSettings.CONFIG: {
            ProjectType.LMS: _SETTINGS_CONFIG,
            ProjectType.CMS: _SETTINGS_CONFIG,
        },
    }
