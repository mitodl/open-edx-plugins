"""Production settings unique to canvas integration plugin."""


from path import Path as path

PLUGIN_TEMPLATES_ROOT = path(__file__).abspath().dirname().dirname()


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""
    settings.CANVAS_ACCESS_TOKEN = settings.AUTH_TOKENS.get(
        "CANVAS_ACCESS_TOKEN", settings.CANVAS_ACCESS_TOKEN
    )
    settings.CANVAS_BASE_URL = settings.ENV_TOKENS.get(
        "CANVAS_BASE_URL", settings.CANVAS_BASE_URL
    )

    settings.TEMPLATES = settings.ENV_TOKENS.get("TEMPLATES", settings.TEMPLATES)

    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT + "/templates")
