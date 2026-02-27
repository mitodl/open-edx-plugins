"""
Tasks for the ol-openedx-course-sync plugin.
"""

from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from django.conf import settings
from edxval.api import copy_course_videos
from opaque_keys.edx.locator import AssetLocator, CourseLocator
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import SignalHandler, modulestore

from ol_openedx_course_sync.apps import OLOpenEdxCourseSyncConfig
from ol_openedx_course_sync.utils import (
    copy_course_content,
    copy_static_tabs,
    get_course_sync_service_user,
    sync_course_handouts,
    sync_course_updates,
    sync_discussions_configuration,
    update_default_tabs,
)

logger = get_task_logger(__name__)


def verify_static_assets(source_course_key, dest_course_key):
    """
    Verify that static assets have been copied successfully.
    """
    logger.info(
        "Verifying static assets for course sync from %s to %s",
        source_course_key,
        dest_course_key,
    )
    source_assets, source_asset_count = (
        modulestore().contentstore.get_all_content_for_course(source_course_key)
    )
    dest_assets, dest_asset_count = (
        modulestore().contentstore.get_all_content_for_course(dest_course_key)
    )
    if source_asset_count != dest_asset_count:
        logger.error(
            "Asset count mismatch: source has %d assets, destination has %d assets",
            source_asset_count,
            dest_asset_count,
        )
        return

    source_assets = {str(asset["asset_key"]): asset for asset in source_assets}
    dest_assets = {str(asset["asset_key"]): asset for asset in dest_assets}

    for asset in source_assets.values():
        dest_asset_key = str(
            AssetLocator(dest_course_key, "asset", asset["content_son"]["name"])
        )
        dest_asset = dest_assets.get(dest_asset_key)
        if not dest_asset:
            logger.error(
                "Missing asset in destination course: %s",
                dest_asset_key,
            )
            return

        if dest_asset["length"] != asset["length"]:
            logger.error(
                "Asset length mismatch for asset %s: source has length %d, destination has length %d",  # noqa: E501
                asset["asset_key"],
                asset["length"],
                dest_asset["length"],
            )


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

    user = get_course_sync_service_user()
    if not user:
        logger.error(
            "Service worker user %s not found. Cannot perform course sync.",
            settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME,
        )
        return

    logger.info(
        "Copying draft course content from %s to %s", source_course_key, dest_course_key
    )
    # Copy draft branch content
    copy_course_content(
        source_course_key, dest_course_key, ModuleStoreEnum.BranchName.draft, user.id
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
        verify_static_assets(source_course_key, dest_course_key)
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
        user.id,
    )

    logger.info("Syncing static tabs from %s to %s", source_course_key, dest_course_key)
    copy_static_tabs(source_course_key, dest_course_key, user)
    update_default_tabs(source_course_key, dest_course_key, user)
    sync_discussions_configuration(source_course_key, dest_course_key, user)
    sync_course_updates(source_course_key, dest_course_key, user)
    sync_course_handouts(source_course_key, dest_course_key, user)

    # trigger course publish signal to trigger outline and relevant updates
    SignalHandler.course_published.send(
        sender=OLOpenEdxCourseSyncConfig, course_key=dest_course_key
    )
    logger.debug(
        "Finished course sync from %s to %s", source_course_key, dest_course_key
    )


@shared_task(
    base=LoggedPersistOnFailureTask,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
)
def async_discussions_configuration_sync(source_course_id, dest_course_id):
    """
    Sync discussions configuration and settings
    from source course to destination course.
    """
    logger.info(
        "Starting discussions configuration sync from %s to %s",
        source_course_id,
        dest_course_id,
    )
    source_course_key = CourseLocator.from_string(source_course_id)
    dest_course_key = CourseLocator.from_string(dest_course_id)

    user = get_course_sync_service_user()
    if not user:
        error_msg = (
            "Service worker user %s not found. "
            "Cannot perform discussions configuration sync."
        )
        logger.error(
            error_msg,
            settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME,
        )
        return

    sync_discussions_configuration(source_course_key, dest_course_key, user)
    logger.info(
        "Finished discussions configuration sync from %s to %s",
        source_course_key,
        dest_course_key,
    )
