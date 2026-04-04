"""Celery tasks for ol-social-auth plugin."""

import logging

from celery import shared_task
from oauth2_provider.models import clear_expired

log = logging.getLogger(__name__)
oauth2_logger = logging.getLogger("oauth2_provider")


@shared_task(acks_late=True)
def clear_expired_tokens():
    """Clear expired OAuth2 access, refresh, and ID tokens."""
    log.info("Starting clear_expired_tokens...")
    # Suppress debug-level logs from oauth2_provider during cleanup.
    # Its batch_delete debug logs lack the 'userid' field expected by
    # Open edX's custom log formatter, causing noisy ValueError tracebacks.
    original_level = oauth2_logger.level
    oauth2_logger.setLevel(logging.INFO)
    try:
        clear_expired()
    finally:
        oauth2_logger.setLevel(original_level)
    log.info("Finished clear_expired_tokens.")
