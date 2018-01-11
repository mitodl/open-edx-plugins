"""
Utility functions for the SGA XBlock
"""
import datetime
import time
import pytz

from django.conf import settings
from django.core.files.storage import default_storage


def utcnow():
    """
    Get current date and time in UTC
    """
    return datetime.datetime.now(tz=pytz.utc)


def is_finalized_submission(submission_data):
    """
    Helper function to determine whether or not a Submission was finalized by the student
    """
    if submission_data and submission_data.get('answer') is not None:
        return submission_data['answer'].get('finalized', True)
    return False


def get_file_modified_time_utc(file_path):
    """
    Gets the UTC timezone-aware modified time of a file at the given file path
    """
    file_timezone = (
        # time.tzname returns a 2 element tuple:
        #   (local non-DST timezone, e.g.: 'EST', local DST timezone, e.g.: 'EDT')
        pytz.timezone(time.tzname[0])
        if settings.DEFAULT_FILE_STORAGE == 'django.core.files.storage.FileSystemStorage'
        else pytz.utc
    )
    return file_timezone.localize(
        default_storage.modified_time(file_path)
    ).astimezone(
        pytz.utc
    )
