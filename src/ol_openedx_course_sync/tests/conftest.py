"""
Pytest configuration for ol_openedx_course_sync tests.
"""

from django.conf import settings


def pytest_configure():
    """Pytest hook that runs after command line options have been parsed"""

    # The LMS-only test modules import lms.djangoapps.instructor_task, which
    # transitively imports bulk_email's tasks and reads these settings at module
    # import time. They are absent under CMS settings, so the import (and with it
    # collection of the whole test session) fails without them -- even though the
    # tests themselves are skipped outside the LMS.
    if not hasattr(settings, "BULK_EMAIL_DEFAULT_RETRY_DELAY"):
        settings.BULK_EMAIL_DEFAULT_RETRY_DELAY = 10
    if not hasattr(settings, "BULK_EMAIL_MAX_RETRIES"):
        settings.BULK_EMAIL_MAX_RETRIES = 5
