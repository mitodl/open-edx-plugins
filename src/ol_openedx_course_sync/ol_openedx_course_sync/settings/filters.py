"""Helper to register the course sync instructor-dashboard tab filter.

Kept separate from ``pipeline`` (which imports xmodule) so it is safe to import
at settings-load time.
"""

INSTRUCTOR_DASHBOARD_TABS_FILTER = (
    "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
)
COURSE_SYNC_TAB_PIPELINE_STEP = (
    "ol_openedx_course_sync.pipeline.AddCourseSyncInstructorTab"
)


def register_instructor_tab_filter(settings):
    """Merge the course sync tab pipeline step into ``OPEN_EDX_FILTERS_CONFIG``.

    Applied from production settings, which is where it has to happen:
    ``lms/envs/production.py`` overwrites ``OPEN_EDX_FILTERS_CONFIG`` wholesale
    from the deployment YAML (``vars().update(...)``), dropping any entry
    registered only in common settings. The merge is idempotent and preserves
    other configured filters and pipeline steps.
    """
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_entry = filters_config.setdefault(
        INSTRUCTOR_DASHBOARD_TABS_FILTER, {"fail_silently": True, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if COURSE_SYNC_TAB_PIPELINE_STEP not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(COURSE_SYNC_TAB_PIPELINE_STEP)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
