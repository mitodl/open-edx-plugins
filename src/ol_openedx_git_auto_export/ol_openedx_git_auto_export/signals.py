import logging

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.template.defaultfilters import slugify
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from openedx_events.content_authoring.data import CourseData
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    RE_RUN_DELAY_TIME,
)
from ol_openedx_git_auto_export.models import CourseGitRepo
from ol_openedx_git_auto_export.tasks import async_export_to_git
from ol_openedx_git_auto_export.utils import (
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
            listen_for_course_created(course=CourseData(course_key=course_key))

        user = get_publisher_username(course_module)
        # If the Git auto-export is enabled, push the course changes to Git
        async_export_to_git.delay(str(course_key), user)


def listen_for_course_created(**kwargs):
    course_id = kwargs.get("course").course_key
    course_id_slugified = slugify(str(course_id))
    if not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION):
        log.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation for course %s",  # noqa: E501
            course_id,
        )
        return None

    # SignalHandler.course_published is called before COURSE_CREATED signal
    if CourseGitRepo.objects.filter(course_id=str(course_id)).exists():
        log.info(
            "GitHub repository already exists for course %s. Skipping creation.",
            course_id,
        )
        return None

    gh_access_token = settings.GITHUB_ACCESS_TOKEN
    if not settings.GITHUB_ORG_API_URL or not gh_access_token:
        error_msg = "GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set in settings. Skipping GitHub repo creation."  # noqa: E501
        raise ImproperlyConfigured(error_msg)

    url = f"{settings.GITHUB_ORG_API_URL}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "name": course_id_slugified,
        "description": f"Git repository for {course_id!s}",
        "private": True,
        "has_issues": False,
        "has_project": False,
        "has_wiki": False,
        "auto_init": True,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 201:  # noqa: PLR2004
        log.error(
            "Failed to create GitHub repository for course %s: %s",
            course_id,
            response.json(),
        )
        return None

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        CourseGitRepo.objects.create(
            course_id=str(course_id),
            git_url=ssh_url,
        )
        log.info(
            "GitHub repository created for course %s: %s",
            course_id,
            ssh_url,
        )
    else:
        log.error(
            "Failed to retrieve SSH URL for GitHub repository for course %s",
            course_id,
        )

    return ssh_url
