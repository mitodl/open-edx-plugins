"""Production settings unique to canvas integration plugin."""

from path import Path as path  # noqa: N813

from ol_openedx_canvas_integration.settings.lms.filters import (
    register_instructor_tab_filter,
)

PLUGIN_TEMPLATES_ROOT = path(__file__).abspath().dirname().dirname().dirname()


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""  # noqa: D401
    settings.CANVAS_ACCESS_TOKEN = settings.AUTH_TOKENS.get(
        "CANVAS_ACCESS_TOKEN", settings.CANVAS_ACCESS_TOKEN
    )
    settings.CANVAS_BASE_URL = settings.ENV_TOKENS.get(
        "CANVAS_BASE_URL", settings.CANVAS_BASE_URL
    )

    # Re-register the instructor-dashboard tab filter. Production overwrites
    # OPEN_EDX_FILTERS_CONFIG wholesale from the deployment YAML, dropping the
    # entry added by common settings; this merges the pipeline step back in.
    register_instructor_tab_filter(settings)

    settings.TEMPLATES = settings.ENV_TOKENS.get("TEMPLATES", settings.TEMPLATES)

    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT + "/templates")
