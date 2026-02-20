"""
AppConfig for ol_openedx_git_auto_export app
"""
# ruff: noqa: E501

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
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_course_created",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.COURSE_CREATED",
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_course_created",
                    },
                    # Library Signals
                    # NOTE: Library v1 (library-v1:) only has LIBRARY_UPDATED, no creation signal
                    # Library v2 (lib:) has:
                    #   - CONTENT_LIBRARY_CREATED/UPDATED: for library metadata changes
                    #   - LIBRARY_BLOCK_CREATED/UPDATED: for block/component changes
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_updated",
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.LIBRARY_UPDATED",  # library v1 update
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_updated",
                    },
                    # lib V2 - Library-level signals
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_v2_created",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.CONTENT_LIBRARY_CREATED",  # library v2 only
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_v2_created",
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_v2_updated",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.CONTENT_LIBRARY_UPDATED",  # library v2 metadata only
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_v2_updated",
                    },
                    # lib V2 - Block-level signals (for component add/update/delete)
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_block_created",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.LIBRARY_BLOCK_CREATED",
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_block_created",
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_block_updated",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.LIBRARY_BLOCK_UPDATED",
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_block_updated",
                    },
                    # NOTE: There are many other signals as well which we might have to add
                    # see: https://github.com/openedx/openedx-events/blob/main/openedx_events/content_authoring/signals.py
                ],
            },
        },
    }
