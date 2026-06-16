"""Common settings unique to the canvas integration plugin."""

from celery.schedules import crontab


def plugin_settings(settings):
    """Canvas integration plugin settings for CMS."""
    settings.CANVAS_ACCESS_TOKEN = None
    settings.CANVAS_BASE_URL = None

    if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
        settings.CELERYBEAT_SCHEDULE = {}
    settings.CELERYBEAT_SCHEDULE["sync_canvas_due_dates"] = {
        "task": "ol_openedx_canvas_integration.cms_tasks.sync_canvas_due_dates_for_all_courses",  # noqa: E501
        "schedule": crontab(minute=0),
    }
