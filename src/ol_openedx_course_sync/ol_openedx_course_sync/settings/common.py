"""Common settings unique to the course sync plugin."""


def plugin_settings(settings):
    """Configure settings for the course sync plugin."""
    # .. setting_name: OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
    # .. setting_default: ""
    # .. setting_description: The username of the service worker that
    # will be used to sync courses.
    settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME = ""
