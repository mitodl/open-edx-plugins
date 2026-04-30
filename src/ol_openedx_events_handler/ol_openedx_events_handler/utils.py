"""Utility functions for the OL Open edX events handler plugin."""

import logging

from django.conf import settings

log = logging.getLogger(__name__)


def validate_enrollment_webhook():
    """
    Validate that the enrollment webhook is properly configured.

    Checks that both ENROLLMENT_WEBHOOK_URL and ENROLLMENT_WEBHOOK_ACCESS_TOKEN
    are set in Django settings.

    Returns:
        bool: True if the webhook is fully configured, False otherwise.
    """
    webhook_url = getattr(settings, "ENROLLMENT_WEBHOOK_URL", None)
    if not webhook_url:
        log.warning(
            "ENROLLMENT_WEBHOOK_URL is not configured. "
            "Skipping enrollment webhook dispatch."
        )
        return False

    webhook_key = getattr(settings, "ENROLLMENT_WEBHOOK_ACCESS_TOKEN", None)
    if not webhook_key:
        log.warning(
            "ENROLLMENT_WEBHOOK_ACCESS_TOKEN is not configured. "
            "Skipping enrollment webhook dispatch."
        )
        return False

    return True


def validate_certificate_webhook():
    """
    Validate that the certificate webhook is properly configured.

    Checks that both the certificate webhook URL and access token are set in
    Django settings.

    Returns:
        bool: True if the webhook is fully configured, False otherwise.
    """
    webhook_url = getattr(settings, "CERTIFICATE_WEBHOOK_URL", None)
    if not webhook_url:
        log.warning(
            "Certificate webhook URL is not configured. "
            "Skipping certificate webhook dispatch."
        )
        return False

    webhook_key = getattr(settings, "CERTIFICATE_WEBHOOK_ACCESS_TOKEN", None)
    if not webhook_key:
        log.warning(
            "Certificate webhook access token is not configured. "
            "Skipping certificate webhook dispatch."
        )
        return False

    return True
