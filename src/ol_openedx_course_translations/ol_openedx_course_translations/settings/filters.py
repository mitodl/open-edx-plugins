# noqa: INP001

"""Register the in-place translation filter steps.

Called from both the common and production LMS settings, because
``lms/envs/production.py`` replaces ``OPEN_EDX_FILTERS_CONFIG`` wholesale from
the deployment YAML and drops entries added by common settings.

Steps fail silently: on an error the platform logs it and the learner sees the
source text, rather than a broken page.
"""

TRANSLATION_PIPELINE_STEPS = {
    "org.openedx.learning.xblock.bound.v1": (
        "ol_openedx_course_translations.filters.TranslateBoundBlock"
    ),
    "org.openedx.learning.course_blocks.transform.completed.v1": (
        "ol_openedx_course_translations.filters.TranslateCourseBlockNames"
    ),
    "org.openedx.learning.course_outline.api.render.started.v1": (
        "ol_openedx_course_translations.filters.TranslateCourseOutline"
    ),
    "org.openedx.learning.course_home_metadata.api.render.started.v1": (
        "ol_openedx_course_translations.filters.TranslateCourseHomeMetadata"
    ),
    "org.openedx.learning.courseware_metadata.api.render.started.v1": (
        "ol_openedx_course_translations.filters.TranslateCoursewareMetadata"
    ),
}


def register_translate_content_filter(settings):
    """Merge the translation steps into ``OPEN_EDX_FILTERS_CONFIG``, idempotently."""
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    for filter_type, step in TRANSLATION_PIPELINE_STEPS.items():
        filter_entry = filters_config.setdefault(
            filter_type, {"fail_silently": True, "pipeline": []}
        )
        filter_entry.setdefault("pipeline", [])
        if step not in filter_entry["pipeline"]:
            filter_entry["pipeline"].append(step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
