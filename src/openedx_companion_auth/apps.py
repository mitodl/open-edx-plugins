"""openedx_companion_auth app config"""

from django.apps import AppConfig


class MITxCoreConfig(AppConfig):
    """App configuration"""

    name = "openedx_companion_auth"
    verbose_name = "Openedx Companion Auth"

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
