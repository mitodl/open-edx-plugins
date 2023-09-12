"""Production settings unique to the rapid response plugin."""

from path import Path as path  # noqa: N813

PLUGIN_TEMPLATES_ROOT = path(__file__).abspath().dirname().dirname()


def plugin_settings(settings):
    """Settings for the rapid response plugin."""  # noqa: D401
    settings.TEMPLATES = settings.ENV_TOKENS.get("TEMPLATES", settings.TEMPLATES)

    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT + "/templates")
