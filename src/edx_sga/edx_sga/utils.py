"""
Utility functions for the SGA XBlock
"""
import datetime
import pytz

from django.conf import settings


def tznow():
    """
    Get current date and time.
    """
    return datetime.datetime.utcnow().replace(
        tzinfo=pytz.timezone(getattr(settings, "TIME_ZONE", pytz.utc.zone))
    )


def is_finalized_submission(submission_data):
    """
    Helper function to determine whether or not a Submission was finalized by the student
    """
    if submission_data and submission_data.get('answer') is not None:
        return submission_data['answer'].get('finalized', True)
    return False
