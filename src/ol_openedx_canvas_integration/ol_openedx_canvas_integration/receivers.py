"""Django Signal handlers."""

import logging

from ol_openedx_canvas_integration.tasks import sync_user_grade_with_canvas
from ol_openedx_canvas_integration.utils import get_cached_canvas_course_id

log = logging.getLogger(__name__)


def update_grade_in_canvas(sender, instance, created, **kwargs):  # noqa: ARG001
    """
    Automatically update grades in Canvas when assignments are synced.

    This signal receiver is wired to the `post_save` signal from the
    lms.djangoapps.grades.models.PersistentSubsectionGrade model. It then
    updates the Canvas course if the subsection is already synced to a Canvas
    course as an assignment.
    """
    if get_cached_canvas_course_id(instance.course_id) is None:
        log.debug(
            "Course %s has no linked Canvas course. Skipping grade sync.",
            instance.course_id,
        )
        return

    log.debug("Grade updated, triggering background task")
    sync_user_grade_with_canvas.delay(instance.id)
