"""Utility functions for the OL Open edX events handler plugin."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def validate_enrollment_webhook():
    """
    Validate that the enrollment webhook is properly configured.

    Checks that both ENROLLMENT_WEBHOOK_URL and ENROLLMENT_WEBHOOK_KEY
    are set in Django settings.

    Returns:
        bool: True if the webhook is fully configured, False otherwise.
    """
    webhook_url = getattr(settings, "ENROLLMENT_WEBHOOK_URL", None)
    webhook_key = getattr(settings, "ENROLLMENT_WEBHOOK_KEY", None)

    if not webhook_url:
        log.warning(
            "ENROLLMENT_WEBHOOK_URL is not configured. "
            "Skipping enrollment webhook dispatch."
        )
        return False

    if not webhook_key:
        log.warning(
            "ENROLLMENT_WEBHOOK_KEY is not configured. "
            "Skipping enrollment webhook dispatch."
        )
        return False

    return True
