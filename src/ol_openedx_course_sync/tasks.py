"""
Tasks for the ol-openedx-course-sync plugin.
"""

from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from edxval.api import copy_course_videos
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import SignalHandler, modulestore

from ol_openedx_course_sync.apps import OLOpenEdxCourseSyncConfig
from ol_openedx_course_sync.utils import (
    copy_course_content,
    copy_static_tabs,
    update_default_tabs,
)

logger = get_task_logger(__name__)


@shared_task(
    base=LoggedPersistOnFailureTask,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
)
def async_course_sync(source_course_id, dest_course_id):
    """
    Sync course content from source course to destination course.
    """
    logger.info("Starting course sync from %s to %s", source_course_id, dest_course_id)
    source_course_key = CourseLocator.from_string(source_course_id)
    dest_course_key = CourseLocator.from_string(dest_course_id)

    logger.info(
        "Copying draft course content from %s to %s", source_course_key, dest_course_key
    )
    # Copy draft branch content
    copy_course_content(
        source_course_key, dest_course_key, ModuleStoreEnum.BranchName.draft
    )

    logger.info(
        "Copying course assets from %s to %s",
        source_course_key,
        dest_course_key,
    )
    # Copy course assets and videos.
    # These steps are taken from the course_rerun task in edx-platform.
    module_store = modulestore()
    if module_store.contentstore:
        module_store.contentstore.delete_all_course_assets(dest_course_key)
        module_store.contentstore.copy_all_course_assets(
            source_course_key, dest_course_key
        )
    copy_course_videos(source_course_key, dest_course_key)

    logger.info(
        "Copying published course content from %s to %s",
        source_course_key,
        dest_course_key,
    )
    # copy published branch content
    copy_course_content(
        source_course_key,
        dest_course_key,
        ModuleStoreEnum.BranchName.published,
    )

    # trigger course publish signal to trigger outline and relevant updates
    SignalHandler.course_published.send(
        sender=OLOpenEdxCourseSyncConfig, course_key=dest_course_key
    )
    logger.debug(
        "Finished course sync from %s to %s", source_course_key, dest_course_key
    )


@shared_task
def sync_course_static_tabs(source_course_id, target_course_id):
    """
    Sync static tabs from source course to target course.
    """
    logger.info("Syncing static tabs from %s to %s", source_course_id, target_course_id)
    source_course_key = CourseLocator.from_string(source_course_id)
    target_course_key = CourseLocator.from_string(target_course_id)

    copy_static_tabs(source_course_key, target_course_key)
    update_default_tabs(source_course_key, target_course_key)

    logger.info(
        "Finished syncing static tabs from %s to %s",
        source_course_key,
        target_course_key,
    )
