from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from cms.djangoapps.contentstore.git_export_utils import GitExportError, export_to_git
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore

LOGGER = get_task_logger(__name__)


@shared_task
def async_export_to_git(course_key_string, user=None):
    """
    Exports a course to Git.
    """
    course_key = CourseKey.from_string(course_key_string)
    course_module = modulestore().get_course(course_key)

    try:
        LOGGER.debug(
            "Starting async course content export to git (course id: %s)",
            course_module.id,
        )
        export_to_git(course_module.id, course_module.giturl, user=user)
    except GitExportError as ex:
        LOGGER.error(
            "Failed async course content export to git (course id: %s): %s",
            course_module.id,
            ex,
        )
    except Exception as ex:  # pylint: disable=broad-except
        LOGGER.error(
            "Unknown error occured during async course content export to git (course id: %s): %s",
            course_module.id,
            ex,
        )
