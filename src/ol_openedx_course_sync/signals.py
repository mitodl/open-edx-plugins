"""
Signal handlers for ol-openedx-course-sync plugin
"""

import logging

from common.djangoapps.course_action_state.models import CourseRerunState
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from openedx_events.content_authoring.data import XBlockData
from openedx_events.content_authoring.signals import (
    XBLOCK_CREATED,
    XBLOCK_DELETED,
    XBLOCK_UPDATED,
)

from ol_openedx_course_sync.constants import COURSE_RERUN_STATE_SUCCEEDED
from ol_openedx_course_sync.models import CourseSyncMapping, CourseSyncOrganization
from ol_openedx_course_sync.tasks import async_course_sync, sync_course_static_tabs

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

    if not settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME:
        log.error(
            "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set. "
            "Course sync will not be performed."
        )
        return

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


@receiver(XBLOCK_CREATED)
@receiver(XBLOCK_DELETED)
@receiver(XBLOCK_UPDATED)
def listen_for_static_tab_changes(**kwargs):
    """
    Listen for the course static tab changes and trigger static tab sync
    """
    xblock_info = kwargs.get("xblock_info")
    if not xblock_info or not isinstance(xblock_info, XBlockData):
        log.error("Received null or incorrect data for event")
        return

    if xblock_info.block_type != "static_tab":
        return

    if not settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME:
        log.error(
            "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set. "
            "Static tab sync will not be performed."
        )
        return

    course_key = xblock_info.usage_key.course_key
    if not CourseSyncOrganization.objects.filter(
        organization=course_key.org, is_active=True
    ).exists():
        return

    course_sync_mappings = CourseSyncMapping.objects.filter(
        source_course=course_key, is_active=True
    )
    if not course_sync_mappings:
        return

    for course_sync_mapping in course_sync_mappings:
        sync_course_static_tabs.delay(
            str(course_sync_mapping.source_course),
            str(course_sync_mapping.target_course),
        )
