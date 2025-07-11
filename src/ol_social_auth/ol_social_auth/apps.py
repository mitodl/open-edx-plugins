from django.apps import AppConfig

settings_location = {"relative_path": "settings.common"}
settings_config = {
    "test": settings_location,
    "common": settings_location,
    "production": settings_location,
    "devstack": settings_location,
}


class OLOpenEdxSocialAuthConfig(AppConfig):
    name = "ol_openedx_social_auth"
    verbose_name = "Social auth plugin for Open edX"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": settings_config,
            "cms.djangoapp": settings_config,
        }
    }
