"""openedx_companion_auth app config"""

from django.apps import AppConfig


class MITxCoreConfig(AppConfig):
    """App configuration"""

    name = "openedx_companion_auth"
    verbose_name = "Openedx Companion Auth"

    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
                "production": {"relative_path": "settings.production"},
            }
        }
    }
