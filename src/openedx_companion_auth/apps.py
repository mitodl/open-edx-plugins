"""mitxpro_extensions app config"""
from __future__ import unicode_literals

from django.apps import AppConfig


class MITxProCoreConfig(AppConfig):
    """App configuration"""

    name = "openedx_companion_auth"
    verbose_name = "MIT xPro Openedx Extensions"

    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "test": {"relative_path": "settings.test"},
                "common": {"relative_path": "settings.common"},
                # aws deprecated in favor of production, see https://openedx.atlassian.net/browse/DEPR-14
                "aws": {"relative_path": "settings.production"},
                "production": {"relative_path": "settings.production"},
            }
        }
    }
