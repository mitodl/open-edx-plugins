"""
Custom exceptions for the ol_openedx_git_auto_export app.
"""


class ContentNotFoundError(Exception):
    """
    Raised when a course or library cannot be found via the modulestore or
    the content_libraries API.

    This is expected to happen transiently right after a course/library is
    created: the creation signal (e.g. CONTENT_LIBRARY_CREATED) can fire
    before the DB transaction that wrote the row has committed, so an async
    Celery task racing against that commit finds nothing.
    """
