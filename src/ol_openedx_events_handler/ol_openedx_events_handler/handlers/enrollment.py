"""Signal handler for course enrollment creation."""

import logging

from crum import get_current_user
from django.conf import settings
from django.db import transaction

log = logging.getLogger(__name__)


def _is_service_worker_enrollment():
    """
    Determine whether the current enrollment was created by the webhook consumer.

    The external system creates its own enrollments by calling the Open edX
    enrollment REST API with an OAuth2 token bound to a dedicated service worker
    account, so Open edX resolves those requests to that account. Notifying the
    system about enrollments it just created itself is redundant, so they are
    filtered out here. ``COURSE_ENROLLMENT_CREATED`` is emitted synchronously
    inside the request that created the enrollment, so the acting user is still
    available through ``crum``.

    When the acting user cannot be resolved (no request context, e.g. a Celery
    task or a management command) or the username is not configured, this
    returns False so the webhook is still dispatched. A redundant webhook is
    harmless because the endpoint is idempotent, whereas dropping a real
    enrollment silently loses data.

    Returns:
        bool: True if the enrollment was created by the service worker.
    """
    service_worker_username = getattr(
        settings, "ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME", None
    )
    if not service_worker_username:
        log.warning(
            "ENROLLMENT_WEBHOOK_SERVICE_WORKER_USERNAME is not configured. "
            "Enrollment webhooks will be dispatched for every enrollment, "
            "including the ones created by the webhook consumer itself."
        )
        return False

    current_username = getattr(get_current_user(), "username", None)
    if not current_username:
        log.info(
            "Could not resolve the acting user for this enrollment. "
            "Dispatching the enrollment webhook."
        )
        return False

    return current_username == service_worker_username


def handle_course_enrollment_created(
    sender,  # noqa: ARG001
    enrollment,
    **kwargs,  # noqa: ARG001
):
    """
    Handle the COURSE_ENROLLMENT_CREATED event.

    When a user is enrolled in a course in Open edX, this handler triggers an
    asynchronous task to notify the webhook provider so the enrollment can be
    mirrored in the corresponding external system. Enrollments that the external
    system created itself are skipped, see ``_is_service_worker_enrollment``.

    Args:
        sender: The sender of the signal.
        enrollment (CourseEnrollmentData): Data about the enrollment, including
            user info, course key and enrollment mode.
        **kwargs: Additional keyword arguments from the signal.
    """
    from ol_openedx_events_handler.tasks import (  # noqa: PLC0415
        notify_course_enrollment_created,
    )
    from ol_openedx_events_handler.utils import (  # noqa: PLC0415
        validate_enrollment_webhook,
    )

    # Checked first so installations that do not use the enrollment webhook at
    # all bail out before any other check logs anything.
    if not validate_enrollment_webhook():
        return

    course_key = str(enrollment.course.course_key)
    if _is_service_worker_enrollment():
        log.debug(
            "Enrollment in course '%s' was created by the webhook consumer. "
            "Skipping enrollment webhook.",
            course_key,
        )
        return

    user_email = enrollment.user.pii.email
    mode = enrollment.mode
    if not user_email:
        log.error(
            "Cannot dispatch enrollment webhook without user email for course '%s'.",
            course_key,
        )
        return

    log.info(
        "User '%s' was enrolled in course '%s' (mode: %s). "
        "Dispatching enrollment webhook.",
        user_email,
        course_key,
        mode,
    )

    def dispatch_webhook():
        """
        Queue the webhook task, logging instead of raising if queueing fails.

        This runs from an ``on_commit`` callback, which fires after the
        enrollment has been committed and outside the event dispatch that
        ``send_robust`` would have shielded. An exception here would therefore
        surface in the caller that created the enrollment -- for the instructor
        dashboard, inside the ``transaction.atomic()`` block in
        ``lms/djangoapps/instructor/utils.py``, which reports it as a failed
        enrollment even though the learner is enrolled and committed. Raising
        can neither undo the enrollment nor re-queue the task, so the only
        useful thing left to do is record it.
        """
        try:
            notify_course_enrollment_created.delay(
                user_email=user_email,
                course_key=course_key,
                mode=mode,
            )
        except Exception:
            log.exception(
                "Failed to queue the enrollment webhook for user '%s' in course '%s'.",
                user_email,
                course_key,
            )

    # The event is emitted inside the transaction that creates the enrollment,
    # so deferring the dispatch avoids notifying the external system about an
    # enrollment that is subsequently rolled back.
    transaction.on_commit(dispatch_webhook)
