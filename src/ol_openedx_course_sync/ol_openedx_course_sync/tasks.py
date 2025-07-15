"""
Tasks for the ol-openedx-course-sync plugin.
"""

from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from django.conf import settings
from django.contrib.auth import get_user_model
from edx_django_utils.cache import TieredCache, get_cache_key
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

User = get_user_model()
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

    cache_key = get_cache_key(
        course_sync_service_worker=settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
    )
    cache_value = TieredCache.get_cached_response(cache_key)
    if not cache_value.is_found:
        user = User.objects.filter(
            username=settings.OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
        ).first()
        TieredCache.set_all_tiers(cache_key, user)
    else:
        user = cache_value.value

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

    # trigger course publish signal to trigger outline and relevant updates
    SignalHandler.course_published.send(
        sender=OLOpenEdxCourseSyncConfig, course_key=dest_course_key
    )
    logger.debug(
        "Finished course sync from %s to %s", source_course_key, dest_course_key
    )
