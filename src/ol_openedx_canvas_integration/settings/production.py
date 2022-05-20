"""Production settings unique to canvas integration plugin."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""
    settings.CANVAS_ACCESS_TOKEN = settings.AUTH_TOKENS.get(
        "CANVAS_ACCESS_TOKEN", settings.CANVAS_ACCESS_TOKEN
    )
    settings.CANVAS_BASE_URL = settings.ENV_TOKENS.get(
        "CANVAS_BASE_URL", settings.CANVAS_BASE_URL
    )

    PLUGIN_TEMPLATES_ROOT = os.path.join(BASE_DIR, "templates")
    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT)
