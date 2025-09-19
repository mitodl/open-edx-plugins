import logging

from django.conf import settings
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_GIT_AUTO_EXPORT,
    RE_RUN_DELAY_TIME,
)
from ol_openedx_git_auto_export.models import CourseGitRepo
from ol_openedx_git_auto_export.tasks import async_export_to_git
from ol_openedx_git_auto_export.utils import (
    create_github_repo,
    get_or_create_git_export_repo_dir,
    get_publisher_username,
)

log = logging.getLogger(__name__)


def listen_for_course_publish(
    sender,  # noqa: ARG001
    course_key,
    **kwargs,  # noqa: ARG001
):  # pylint: disable=unused-argument
    """
    Receives publishing signal and performs publishing related workflows
    """

    if settings.FEATURES.get("ENABLE_EXPORT_GIT") and settings.FEATURES.get(
        ENABLE_GIT_AUTO_EXPORT
    ):
        course_module = modulestore().get_course(course_key)
        get_or_create_git_export_repo_dir()
        log.info(
            "Course published with auto-export enabled. Starting export... (course id: %s)",  # noqa: E501
            course_key,
        )
        # HACK: To create auto git repo for Re-runs as it does not emit COURSE_CREATED signal  # noqa: E501 FIX004
        # if course_overview.created and course_module.published_on has difference of less than 2 minutes  # noqa: E501
        # Consider creating Giturl for the course if it doesn't exist
        course_overview = CourseOverview.get_from_id(course_key)
        time_difference = course_module.published_on - course_overview.created
        if (
            time_difference.total_seconds() < RE_RUN_DELAY_TIME
            and not CourseGitRepo.objects.filter(course_id=str(course_key)).exists()
        ):
            log.info(
                "Creating GitHub repository for course (Re-run) %s",
                course_key,
            )
            create_github_repo(course_id=course_key)

        user = get_publisher_username(course_module)
        # If the Git auto-export is enabled, push the course changes to Git
        async_export_to_git.delay(str(course_key), user)


def listen_for_course_created(**kwargs):
    """
    Handle course created signal to create a GitHub repository for the course
    """
    course_key = kwargs.get("course").course_key

    create_github_repo(course_key)
