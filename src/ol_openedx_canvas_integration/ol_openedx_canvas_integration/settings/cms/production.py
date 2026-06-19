"""Production settings unique to canvas integration plugin."""

from celery.schedules import crontab


def plugin_settings(settings):
    """Canvas integration plugin settings for CMS."""
    settings.CANVAS_ACCESS_TOKEN = settings.AUTH_TOKENS.get(
        "CANVAS_ACCESS_TOKEN", settings.CANVAS_ACCESS_TOKEN
    )
    settings.CANVAS_BASE_URL = settings.ENV_TOKENS.get(
        "CANVAS_BASE_URL", settings.CANVAS_BASE_URL
    )

    if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
        settings.CELERYBEAT_SCHEDULE = {}

    settings.CELERYBEAT_SCHEDULE["sync_canvas_due_dates"] = {
        "task": "ol_openedx_canvas_integration.cms_tasks.sync_canvas_due_dates_for_all_courses",  # noqa: E501
        "schedule": crontab(minute=0),
    }
