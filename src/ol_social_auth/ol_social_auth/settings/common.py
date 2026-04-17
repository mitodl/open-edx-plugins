"""Common settings for the ol-social-auth plugin."""

from celery.schedules import crontab


def plugin_settings(settings):
    """Settings for the ol-social-auth plugin."""  # noqa: D401
    settings.OAUTH2_PROVIDER["REFRESH_TOKEN_EXPIRE_SECONDS"] = (
        30 * 24 * 60 * 60  # 30 days
    )
    # Add ol_clear_expired_tokens to the Celery beat schedule.
    if not hasattr(settings, "CELERYBEAT_SCHEDULE"):
        settings.CELERYBEAT_SCHEDULE = {}
    settings.CELERYBEAT_SCHEDULE["ol_clear_expired_tokens"] = {
        "task": "ol_social_auth.tasks.ol_clear_expired_tokens",
        "schedule": crontab(hour=9, minute=0, day_of_week="monday"),
    }
