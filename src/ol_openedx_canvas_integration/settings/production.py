"""Production settings unique to canvas integration plugin."""


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""
    settings.CANVAS_ACCESS_TOKEN = settings.AUTH_TOKENS.get(
        "CANVAS_ACCESS_TOKEN", settings.CANVAS_ACCESS_TOKEN
    )
    settings.CANVAS_BASE_URL = settings.ENV_TOKENS.get(
        "CANVAS_BASE_URL", settings.CANVAS_BASE_URL
    )
