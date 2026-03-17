"""Celery tasks for ol-social-auth plugin."""

import logging

from celery import shared_task

log = logging.getLogger(__name__)


@shared_task(acks_late=True)
def clear_expired_tokens():
    """Clear expired OAuth2 access, refresh, and ID tokens."""
    log.info("Starting clear_expired_tokens...")
    from django.core.management import call_command

    call_command(
        "edx_clear_expired_tokens",
        batch_size=500000,
        sleep_time=2,
    )
    log.info("Finished clear_expired_tokens.")
