# noqa: INP001

"""Register the in-place translation filter steps.

Called from both the common and production LMS settings, because
``lms/envs/production.py`` replaces ``OPEN_EDX_FILTERS_CONFIG`` wholesale from
the deployment YAML and drops entries added by common settings.
"""

TRANSLATION_PIPELINE_STEPS = {
    "org.openedx.learning.vertical_block_child.render.started.v1": (
        "ol_openedx_course_translations.filters.TranslateVerticalChildContent"
    ),
    "org.openedx.learning.xblock.handler.started.v1": (
        "ol_openedx_course_translations.filters.TranslateBlockBeforeHandler"
    ),
}


def register_translate_content_filter(settings):
    """Merge the translation steps into ``OPEN_EDX_FILTERS_CONFIG``, idempotently."""
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    for filter_type, step in TRANSLATION_PIPELINE_STEPS.items():
        filter_entry = filters_config.setdefault(
            filter_type, {"fail_silently": False, "pipeline": []}
        )
        filter_entry.setdefault("pipeline", [])
        if step not in filter_entry["pipeline"]:
            filter_entry["pipeline"].append(step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
