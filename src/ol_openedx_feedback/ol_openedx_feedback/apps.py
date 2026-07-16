"""ol_openedx_feedback Django application initialization."""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class OLOpenedxFeedbackConfig(AppConfig):
    """Configuration for the ol_openedx_feedback Django application.

    Trigger-only plugin: the feedback trigger is registered via the
    ``xblock_asides.v1`` entry point (no URLs or models — feedback is persisted
    in mit-learn and the MFE owns the submit URL). The only Django settings are
    the plugin defaults populated by ``settings.common``.
    """

    name = "ol_openedx_feedback"
    verbose_name = "Open edX Block Feedback"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.LMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
            ProjectType.CMS: {
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            },
        },
    }
