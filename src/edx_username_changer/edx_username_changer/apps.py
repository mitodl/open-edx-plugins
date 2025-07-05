"""
App configuration for edx-username-changer plugin
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSignals
from openedx.core.djangoapps.plugins.constants import (
    ProjectType,
)


class EdxUsernameChangerConfig(AppConfig):
    name = "edx_username_changer"
    verbose_name = "Open edX Username Changer"

    plugin_app = {
        PluginSignals.CONFIG: {
            ProjectType.LMS: {
                PluginSignals.RECEIVERS: [
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "user_pre_save_callback",
                        PluginSignals.SIGNAL_PATH: "django.db.models.signals.pre_save",
                        PluginSignals.SENDER_PATH: "django.contrib.auth.models.User",
                    },
                    {
                        PluginSignals.RECEIVER_FUNC_NAME: "user_post_save_callback",
                        PluginSignals.SIGNAL_PATH: "django.db.models.signals.post_save",
                        PluginSignals.SENDER_PATH: "django.contrib.auth.models.User",
                    },
                ],
            },
        },
    }
