"""Celery tasks for the OL Open edX events handler plugin."""

from ol_openedx_events_handler.tasks.certificate_passing import (  # noqa: F401
    create_certificate_for_passing_grade,
)
from ol_openedx_events_handler.tasks.course_access_role import (  # noqa: F401
    notify_course_access_role_addition,
)
