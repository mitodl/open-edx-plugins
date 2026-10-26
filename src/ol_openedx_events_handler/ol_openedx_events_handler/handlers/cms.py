"""CMS-only signal handlers exported for plugin signal registration."""

from ol_openedx_events_handler.handlers.course_access_role import (
    handle_course_access_role_added,
)
from ol_openedx_events_handler.handlers.role_assignment import (
    handle_role_assignment_created,
)

__all__ = [
    "handle_course_access_role_added",
    "handle_role_assignment_created",
]
