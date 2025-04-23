from django.apps import AppConfig

sentry_settings_location = {"relative_path": "settings.sentry"}
sentry_settings_config = {
    "test": sentry_settings_location,
    "common": sentry_settings_location,
    "production": sentry_settings_location,
    "devstack": sentry_settings_location,
}


class EdxSentry(AppConfig):
    name = "ol_openedx_sentry"
    verbose_name = "Sentry integration for Open edX"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": sentry_settings_config,
            "cms.djangoapp": sentry_settings_config,
        }
    }
