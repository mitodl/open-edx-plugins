"""
Tasks for the ol-openedx-course-sync plugin.
"""

from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from celery_utils.persist_on_failure import LoggedPersistOnFailureTask
from opaque_keys.edx.locator import CourseLocator
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import SignalHandler

from ol_openedx_course_sync.apps import OLOpenEdxCourseSyncConfig
from ol_openedx_course_sync.utils import copy_course_content

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
