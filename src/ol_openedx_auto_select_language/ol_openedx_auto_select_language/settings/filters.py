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
