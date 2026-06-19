"""Common settings unique to the canvas integration plugin."""


def plugin_settings(settings):
    """Settings for the canvas integration plugin."""  # noqa: D401
    settings.CANVAS_ACCESS_TOKEN = None
    settings.CANVAS_BASE_URL = None

    # Register the instructor-dashboard tab filter so the "Canvas" tab is only
    # shown for courses linked to Canvas (canvas_id set in advanced settings).
    # Merge into any existing OPEN_EDX_FILTERS_CONFIG rather than overwriting it.
    filters_config = getattr(settings, "OPEN_EDX_FILTERS_CONFIG", {}) or {}
    filter_key = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
    pipeline_step = "ol_openedx_canvas_integration.pipeline.AddCanvasInstructorTab"
    filter_entry = filters_config.setdefault(
        filter_key, {"fail_silently": True, "pipeline": []}
    )
    filter_entry.setdefault("pipeline", [])
    if pipeline_step not in filter_entry["pipeline"]:
        filter_entry["pipeline"].append(pipeline_step)
    settings.OPEN_EDX_FILTERS_CONFIG = filters_config
