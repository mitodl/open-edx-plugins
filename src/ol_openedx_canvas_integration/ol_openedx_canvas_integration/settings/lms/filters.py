"""Helper to register the Canvas instructor-dashboard tab filter.

Kept separate from ``pipeline`` (which imports xmodule) so it is safe to import
at settings-load time, and shared by both the common and production settings.
"""

INSTRUCTOR_DASHBOARD_TABS_FILTER = (
    "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
)
CANVAS_TAB_PIPELINE_STEP = (
    "ol_openedx_canvas_integration.pipeline.AddCanvasInstructorTab"
)


def register_instructor_tab_filter(settings):
    """Merge the Canvas tab pipeline step into ``OPEN_EDX_FILTERS_CONFIG``.

    Applied from both common and production settings. Production must re-apply it
    because ``lms/envs/production.py`` overwrites ``OPEN_EDX_FILTERS_CONFIG``
    wholesale from the deployment YAML (``vars().update(...)``), which drops any
    entry registered only in common settings. The merge is idempotent and
    preserves other configured filters and pipeline steps.
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_entry = filters_config.setdefault(
        INSTRUCTOR_DASHBOARD_TABS_FILTER, {"fail_silently": True, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if CANVAS_TAB_PIPELINE_STEP not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(CANVAS_TAB_PIPELINE_STEP)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
