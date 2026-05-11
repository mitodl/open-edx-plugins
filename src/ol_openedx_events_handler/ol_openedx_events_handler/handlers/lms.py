"""LMS-only signal handlers exported for plugin signal registration."""

from ol_openedx_events_handler.handlers.course_access_role import (
    handle_course_access_role_added,
)
from ol_openedx_events_handler.receivers.certificate_passing_receiver import (
    listen_for_passing_grade,
)

__all__ = ["handle_course_access_role_added", "listen_for_passing_grade"]
