# noqa: INP001

"""Helper to register the auto-select-language video render filter.

Shared by the common (lms) and production settings so the pipeline step is
declared once. Production must re-apply it because ``lms/envs/production.py``
overwrites ``OPEN_EDX_FILTERS_CONFIG`` wholesale from the deployment YAML
(``vars().update(...)``), which drops any entry registered only in common settings.
"""

XBLOCK_RENDER_STARTED_FILTER = "org.openedx.learning.xblock.render.started.v1"
VIDEO_LANGUAGE_PIPELINE_STEP = (
    "ol_openedx_auto_select_language.filters.AddDestLangForVideoBlock"
)


def register_video_language_filter(settings):
    """Merge the video-language render step into ``OPEN_EDX_FILTERS_CONFIG``.

    Idempotent and preserves other configured filters and pipeline steps (e.g.
    other plugins contributing to the same render.started filter).
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_entry = filters_config.setdefault(
        XBLOCK_RENDER_STARTED_FILTER, {"fail_silently": False, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if VIDEO_LANGUAGE_PIPELINE_STEP not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(VIDEO_LANGUAGE_PIPELINE_STEP)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config


VERTICAL_CHILD_RENDER_STARTED_FILTER = (
    "org.openedx.learning.vertical_block_child.render.started.v1"
)
RESTRICT_TRANSCRIPTS_PIPELINE_STEP = (
    "ol_openedx_auto_select_language.filters.RestrictVideoTranscriptLanguages"
)


def register_restrict_transcripts_filter(settings):
    """Merge the transcript-restriction step into ``OPEN_EDX_FILTERS_CONFIG``.

    Idempotent and preserves other configured filters and pipeline steps, for
    the same reason as ``register_video_language_filter``.
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_entry = filters_config.setdefault(
        VERTICAL_CHILD_RENDER_STARTED_FILTER,
        {"fail_silently": False, "pipeline": []},
    )
    filter_entry.setdefault("pipeline", [])
    if RESTRICT_TRANSCRIPTS_PIPELINE_STEP not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(RESTRICT_TRANSCRIPTS_PIPELINE_STEP)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config


TRANSLATION_PIPELINE_STEPS = {
    "org.openedx.learning.xblock.bound.v1": (
        "ol_openedx_auto_select_language.translation_filters.TranslateBoundBlock"
    ),
    "org.openedx.learning.course_blocks.transform.completed.v1": (
        "ol_openedx_auto_select_language.translation_filters.TranslateCourseBlockNames"
    ),
    "org.openedx.learning.course_outline.api.render.started.v1": (
        "ol_openedx_auto_select_language.translation_filters.TranslateCourseOutline"
    ),
    "org.openedx.learning.course_home_metadata.api.render.started.v1": (
        "ol_openedx_auto_select_language.translation_filters.TranslateCourseHomeMetadata"
    ),
    "org.openedx.learning.courseware_metadata.api.render.started.v1": (
        "ol_openedx_auto_select_language.translation_filters.TranslateCoursewareMetadata"
    ),
    "org.openedx.learning.vertical_block.render.completed.v1": (
        "ol_openedx_auto_select_language.translation_filters.AddAnswerNoteBelowTitles"
    ),
}


def register_translation_filters(settings):
    """Merge the translation display steps into ``OPEN_EDX_FILTERS_CONFIG``.

    These steps fail silently: on an error the platform logs it and the learner
    sees the source text, rather than a broken page.
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    for filter_type, step in TRANSLATION_PIPELINE_STEPS.items():
        filter_entry = filters_config.setdefault(
            filter_type, {"fail_silently": True, "pipeline": []}
        )
        filter_entry.setdefault("pipeline", [])
        if step not in filter_entry["pipeline"]:
            filter_entry["pipeline"].append(step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
