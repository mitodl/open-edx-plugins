"""Production settings unique to the course sync plugin."""

from ol_openedx_course_sync.settings.filters import register_instructor_tab_filter


def plugin_settings(settings):
    """Configure settings for the course sync plugin."""
    env_tokens = getattr(settings, "ENV_TOKENS", {})
    # .. setting_name: OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
    # .. setting_default: ""
    # .. setting_description: The username of the service worker that
    # will be used to sync courses.
    settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME = env_tokens.get(
        "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME", ""
    )

    # Register the instructor-dashboard tab filter. Production overwrites
    # OPEN_EDX_FILTERS_CONFIG wholesale from the deployment YAML, so the entry has
    # to be merged back in here. Only consulted by the LMS; a no-op in the CMS.
    register_instructor_tab_filter(settings)
