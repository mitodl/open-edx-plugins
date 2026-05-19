"""
Pytest configuration for ol_openedx_canvas_integration tests.
"""

from django.conf import settings


def pytest_configure():
    """Pytest hook that runs after command line options have been parsed"""

    # Add additional Django settings needed for the plugin tests
    if not hasattr(settings, "BULK_EMAIL_DEFAULT_RETRY_DELAY"):
        settings.BULK_EMAIL_DEFAULT_RETRY_DELAY = 10
    if not hasattr(settings, "BULK_EMAIL_MAX_RETRIES"):
        settings.BULK_EMAIL_MAX_RETRIES = 5
