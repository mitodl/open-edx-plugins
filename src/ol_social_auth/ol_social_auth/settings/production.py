"""Production settings for the ol-social-auth plugin."""

from celery.schedules import crontab


def plugin_settings(settings):
    """Production overrides for ol-social-auth plugin."""
    # Re-add the celery beat schedule here because the YAML config loading
    # in production.py replaces the entire CELERYBEAT_SCHEDULE dict,
    # wiping out what common.py set. This runs after YAML loading.
    if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
        settings.CELERYBEAT_SCHEDULE = {}
    settings.CELERYBEAT_SCHEDULE["ol_clear_expired_tokens"] = {
        "task": "ol_social_auth.tasks.ol_clear_expired_tokens",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    }
