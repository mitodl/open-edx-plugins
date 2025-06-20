"""Django Signal handlers."""

import logging

from ol_openedx_canvas_integration.tasks import sync_user_grade_with_canvas

log = logging.getLogger(__name__)


def update_grade_in_canvas(sender, instance, created, **kwargs):  # noqa: ARG001
    """
    Automatically update grades in Canvas when assignments are synced.

    This signal receiver is wired to the `post_save` signal from the
    lms.djangoapps.grades.models.PersistentSubsectionGrade model. It then
    updates the Canvas course if the subsection is already synced to a Canvas
    course as an assignment.
    """
    log.debug("Grade updated, triggering background task")
    sync_user_grade_with_canvas.delay(instance.id)
