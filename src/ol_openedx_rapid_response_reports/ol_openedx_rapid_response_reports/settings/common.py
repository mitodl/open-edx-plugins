"""Common settings unique to the rapid response reports plugin."""

from ol_openedx_rapid_response_reports.settings.filters import (
    register_instructor_tab_filter,
)


def plugin_settings(settings):
    """Settings for the rapid response reports plugin."""  # noqa: D401
    # Register the instructor-dashboard tab filter so the "Rapid Responses" tab
    # is added only on deployments where this plugin is installed.
    register_instructor_tab_filter(settings)
