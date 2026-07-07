"""Production settings unique to the rapid response plugin."""

from path import Path as path  # noqa: N813

from ol_openedx_rapid_response_reports.settings.filters import (
    register_instructor_tab_filter,
)

PLUGIN_TEMPLATES_ROOT = path(__file__).abspath().dirname().dirname()


def plugin_settings(settings):
    """Settings for the rapid response plugin."""  # noqa: D401
    # Re-register the instructor-dashboard tab filter. Production overwrites
    # OPEN_EDX_FILTERS_CONFIG wholesale from the deployment YAML, dropping the
    # entry added by common settings; this merges the pipeline step back in.
    register_instructor_tab_filter(settings)

    settings.TEMPLATES = settings.ENV_TOKENS.get("TEMPLATES", settings.TEMPLATES)

    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT + "/templates")
