"""
Signal handlers for ol-openedx-course-sync plugin
"""

import logging

from common.djangoapps.course_action_state.models import CourseRerunState
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

from ol_openedx_course_sync.constants import COURSE_RERUN_STATE_SUCCEEDED
from ol_openedx_course_sync.models import CourseSyncMapping, CourseSyncOrganization
from ol_openedx_course_sync.tasks import async_course_sync

log = logging.getLogger(__name__)


def listen_for_course_publish(
    sender,  # noqa: ARG001
    course_key,
    **kwargs,  # noqa: ARG001
):
    """
    Listen for course publish signal and trigger course sync task
    """
    if not CourseSyncOrganization.objects.filter(
        organization=course_key.org, is_active=True
    ).exists():
        return

    if not getattr(settings, "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME", None):
        error_msg = (
            "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set. "
            "Course sync will not be performed."
        )
        raise ImproperlyConfigured(error_msg)

    course_sync_mappings = CourseSyncMapping.objects.filter(
        source_course=course_key, is_active=True
    )
    if not course_sync_mappings:
        log.info("No mapping found for course %s. Skipping sync.", str(course_key))
        return

    for course_sync_mapping in course_sync_mappings:
        log.info(
            "Initializing course content sync from %s to %s",
            course_sync_mapping.source_course,
            course_sync_mapping.target_course,
        )
        async_course_sync.delay(
            str(course_sync_mapping.source_course),
            str(course_sync_mapping.target_course),
        )


@receiver(post_save, sender=CourseRerunState)
def listen_for_course_rerun_state_post_save(sender, instance, **kwargs):  # noqa: ARG001
    """
    Listen for `CourseRerunState` post_save and
    create target courses in `CourseSyncMapping`
    """
    if instance.state != COURSE_RERUN_STATE_SUCCEEDED:
        return

    if not CourseSyncOrganization.objects.filter(
        organization=instance.source_course_key.org, is_active=True
    ).exists():
        return

    try:
        course_sync_mapping = CourseSyncMapping.objects.create(
            source_course=instance.source_course_key,
            target_course=instance.course_key,
        )
    except ValidationError:
        log.exception(
            "Failed to create CourseSyncMapping for %s",
            instance.source_course_key,
        )
    else:
        # Trigger course sync to sync the published changes.
        # When a course clone or rerun is created, published changes are not synced.
        async_course_sync.delay(
            str(course_sync_mapping.source_course),
            str(course_sync_mapping.target_course),
        )
