"""Production settings unique to the external checkout plugin."""


def plugin_settings(settings):
    """Settings for the external checkout plugin."""
    settings.MARKETING_SITE_CHECKOUT_URL = settings.ENV_TOKENS.get(
        "MARKETING_SITE_CHECKOUT_URL", settings.MARKETING_SITE_CHECKOUT_URL
    )
