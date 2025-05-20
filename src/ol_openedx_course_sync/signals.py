"""
Signal handlers for ol-openedx-course-sync plugin
"""

import logging

from common.djangoapps.course_action_state.models import CourseRerunState
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver
from ol_openedx_course_sync.constants import COURSE_RERUN_STATE_SUCCEEDED
from ol_openedx_course_sync.models import CourseSyncMap, CourseSyncParentOrg
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
    if not CourseSyncParentOrg.objects.filter(organization=course_key.org).exists():
        return

    course_sync_map = CourseSyncMap.objects.filter(source_course=course_key).first()
    if not (course_sync_map and course_sync_map.target_courses):
        log.info("No mapping found for course %s. Skipping copy.", str(course_key))
        return

    source_course = str(course_sync_map.source_course)
    target_keys = [
        key for key in course_sync_map.target_courses.strip().split(",") if key
    ]
    for target_course_key in target_keys:
        log.info(
            "Initializing async course content sync from %s to %s",
            source_course,
            target_course_key,
        )
        async_course_sync.delay(source_course, target_course_key)


@receiver(post_save, sender=CourseRerunState)
def listen_for_course_rerun_state_post_save(sender, instance, **kwargs):  # noqa: ARG001
    """
    Listen for `CourseRerunState` post_save and update target courses in `CourseSyncMap`
    """
    if instance.state != COURSE_RERUN_STATE_SUCCEEDED:
        return

    if not CourseSyncParentOrg.objects.filter(
        organization=instance.source_course_key.org
    ).exists():
        return

    try:
        course_sync_map, _ = CourseSyncMap.objects.get_or_create(
            source_course=instance.source_course_key
        )
    except ValidationError:
        log.exception(
            "Failed to create CourseSyncMap for %s",
            instance.source_course_key,
        )
        return

    target_courses = course_sync_map.target_course_keys
    target_courses.append(str(instance.course_key))
    course_sync_map.target_courses = ",".join(target_courses)

    try:
        course_sync_map.save()
    except ValidationError:
        log.exception(
            "Failed to update CourseSyncMap for %s",
            instance.source_course_key,
        )
    else:
        log.info(
            "Added course %s to target courses for %s",
            instance.course_key,
            instance.source_course_key,
        )
