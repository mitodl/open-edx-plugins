"""
AppConfig for ol_openedx_git_auto_export app
"""

from django.apps import AppConfig
from edx_django_utils.plugins import PluginSettings, PluginSignals
from openedx.core.djangoapps.plugins.constants import ProjectType, SettingsType


class GitAutoExportConfig(AppConfig):
    """
    App config for ol_openedx_git_auto_export django application.
    """

    name = "ol_openedx_git_auto_export"

    plugin_app = {
        PluginSettings.CONFIG: {
            ProjectType.CMS: {
                SettingsType.PRODUCTION: {
                    PluginSettings.RELATIVE_PATH: "settings.production"
                },
                SettingsType.COMMON: {PluginSettings.RELATIVE_PATH: "settings.common"},
            }
        },
        PluginSignals.CONFIG: {
            ProjectType.CMS: {
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_course_publish",
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.COURSE_PUBLISHED",
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_course_publish",
                    }
                ],
            },
        },
    }
