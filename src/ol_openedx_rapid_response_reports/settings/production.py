"""Production settings unique to the rapid response plugin."""

import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))


def plugin_settings(settings):
    """Settings for the rapid response plugin."""
    PLUGIN_TEMPLATES_ROOT = os.path.join(BASE_DIR, "templates")
    for template_engine in settings.TEMPLATES:
        template_dirs = template_engine["DIRS"]
        template_dirs.append(PLUGIN_TEMPLATES_ROOT)
