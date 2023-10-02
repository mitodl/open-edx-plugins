"""
edx_sysadmin Django application initialization.
"""
from django.apps import AppConfig


class EdxSysAdminConfig(AppConfig):
    """
    Configuration for the edx_sysadmin Django application.
    """

    name = "edx_sysadmin"
    verbose_name = "Open edX SysAdmin"

    plugin_app = {
        "url_config": {
            "lms.djangoapp": {
                "namespace": "sysadmin",
                "regex": "^sysadmin/",
            }
        },
        "settings_config": {
            "lms.djangoapp": {
                "common": {"relative_path": "settings.common"},
            }
        },
    }
