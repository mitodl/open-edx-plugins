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
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.COURSE_PUBLISHED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_course_publish",  # noqa: E501
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_course_created",
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.COURSE_CREATED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_course_created",  # noqa: E501
                    },
                    # Library Signals
                    # NOTE: Library v1 (library-v1:) only has LIBRARY_UPDATED, no creation signal  # noqa: E501
                    # Library v2 (lib:) has:
                    #   - CONTENT_LIBRARY_CREATED/UPDATED: for library metadata changes
                    #   - LIBRARY_BLOCK_CREATED/UPDATED: for block/component changes
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_updated",
                        PluginSignals.SIGNAL_PATH: "xmodule.modulestore.django.LIBRARY_UPDATED",  # noqa: E501, library v1 update
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_updated",  # noqa: E501
                    },
                    # lib V2 - Library-level signals
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_v2_created",  # noqa: E501
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.CONTENT_LIBRARY_CREATED",  # noqa: E501, library v2 only
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_v2_created",  # noqa: E501
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_v2_updated",  # noqa: E501
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.CONTENT_LIBRARY_UPDATED",  # noqa: E501, library v2 metadata only
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_v2_updated",  # noqa: E501
                    },
                    # lib V2 - Block-level signals (for component add/update/delete)
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_block_created",  # noqa: E501
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.LIBRARY_BLOCK_CREATED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_block_created",  # noqa: E501
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "listen_for_library_block_updated",  # noqa: E501
                        PluginSignals.SIGNAL_PATH: "openedx_events.content_authoring.signals.LIBRARY_BLOCK_UPDATED",  # noqa: E501
                        PluginSignals.DISPATCH_UID: "ol_openedx_git_auto_export.signals.listen_for_library_block_updated",  # noqa: E501
                    },
                ],
            },
        },
    }
