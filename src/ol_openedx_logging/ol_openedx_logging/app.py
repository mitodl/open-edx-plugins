from django.apps import AppConfig


class EdxLoggingLMS(AppConfig):
    name = "ol_openedx_logging"
    verbose_name = "Log customization support for Open edX platform"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {"production": {"relative_path": "settings.production"}}
        }
    }


class EdxLoggingCMS(AppConfig):
    name = "ol_openedx_logging"
    verbose_name = "Log customization support for Open edX platform"
    plugin_app = {
        "settings_config": {
            "cms.djangoapp": {"production": {"relative_path": "settings.production"}}
        }
    }
