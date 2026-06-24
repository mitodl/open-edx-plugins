"""Common settings unique to the rapid response reports plugin."""


def plugin_settings(settings):
    """Settings for the rapid response reports plugin."""  # noqa: D401
    # Register the instructor-dashboard tab filter so the "Rapid Responses" tab
    # is added only on deployments where this plugin is installed. Merge into any
    # existing OPEN_EDX_FILTERS_CONFIG rather than overwriting it.
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_key = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
    pipeline_step = (
        "ol_openedx_rapid_response_reports.pipeline.AddRapidResponseInstructorTab"
    )
    filter_entry = filters_config.setdefault(
        filter_key, {"fail_silently": True, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if pipeline_step not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(pipeline_step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
