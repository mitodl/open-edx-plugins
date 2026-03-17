"""Common settings for the ol-social-auth plugin."""

from celery.schedules import crontab


def plugin_settings(settings):
    """Add clear_expired_tokens to the Celery beat schedule."""
    settings.OAUTH2_PROVIDER["REFRESH_TOKEN_EXPIRE_SECONDS"] = (
        30 * 24 * 60 * 60  # 30 days
    )
    if not hasattr(settings, "CELERY_BEAT_SCHEDULE"):
        settings.CELERY_BEAT_SCHEDULE = {}
    settings.CELERY_BEAT_SCHEDULE["clear_expired_tokens"] = {
        "task": "ol_social_auth.tasks.clear_expired_tokens",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    }
