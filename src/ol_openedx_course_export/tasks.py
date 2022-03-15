"""
This file contains celery tasks related to S3 course export plugin.
"""
import logging

from botocore.exceptions import ClientError
from celery import shared_task  # pylint: disable=import-error
from cms.djangoapps.contentstore.tasks import CourseExportTask, create_export_tarball
from opaque_keys.edx.keys import CourseKey
from user_tasks.models import UserTaskStatus
from xmodule.modulestore.django import modulestore

from ol_openedx_course_export.s3_client import S3Client

log = logging.getLogger(__name__)


@shared_task(base=CourseExportTask, bind=True)
def task_upload_course_s3(self, user_id, course_key_string):
    """
    A task to generate course tarball and upload to s3 bucket, Also creates task status object to keep track of the
    task updates.
    The status update implementation of (UserTaskStatus) edX also sends an email to the initiator of the export request
    upon completion.

    Args:
        user_id (int): Id of the user who initiated the request
        course_key_string (str): Key of the course to be uploaded

    Returns:
        task_id, Just starts a task and returns it's id as part of Celery's base implementation. Used for status updates
    """
    try:
        self.status.set_state(UserTaskStatus.IN_PROGRESS)
        s3_client = S3Client()
        course_key = CourseKey.from_string(course_key_string)
        module_store = modulestore()
        course_module = module_store.get_course(course_key)
        course_tarball = create_export_tarball(course_module, course_key, {}, None)
        s3_client.upload_course_s3(
            course_tar=course_tarball, course_id=course_key_string
        )
        self.status.set_state(UserTaskStatus.SUCCEEDED)
    except ClientError as ex:
        log.exception(
            f"Course export {course_key_string}: A ClientError in course export:"
        )
        if self.status.state != UserTaskStatus.FAILED:
            self.status.fail({"raw_error_msg": str(ex)})
