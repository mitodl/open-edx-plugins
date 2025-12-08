"""
Celery tasks for asynchronous git export operations.

This module defines background tasks that handle the actual export of course
content to Git repositories using Celery for asynchronous processing.
"""

import requests
from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from cms.djangoapps.contentstore.git_export_utils import GitExportError, export_to_git
from django.conf import settings
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.models import CourseGitRepository
from ol_openedx_git_auto_export.utils import (
    export_course_to_git,
    github_repo_name_format,
    is_auto_repo_creation_enabled,
)

LOGGER = get_task_logger(__name__)


@shared_task
def async_export_to_git(course_key_string, user=None):
    """
    Exports a course to Git.
    """  # noqa: D401
    course_key = CourseKey.from_string(course_key_string)
    course_module = modulestore().get_course(course_key)

    try:
        course_repo = CourseGitRepository.objects.get(course_key=course_key)
        if course_repo.is_export_enabled:
            LOGGER.info(
                "Starting async course content export to git (course id: %s)",
                course_module.id,
            )
            export_to_git(course_module.id, course_repo.git_url, user=user)
        else:
            LOGGER.info(
                "Git export is disabled for course %s. Skipping export.",
                course_key_string,
            )
    except GitExportError:
        LOGGER.exception(
            "Failed async course content export to git (course id: %s)",
            course_module.id,
        )
    except CourseGitRepository.DoesNotExist:
        LOGGER.exception(
            "CourseGitRepository does not exist for course %s."
            "Creating repository and exporting course content.",
            course_key_string,
        )
        if is_auto_repo_creation_enabled():
            async_create_github_repo.delay(str(course_key), export_course=True)
    except Exception:
        LOGGER.exception(
            "Unknown error occured during async course content export to git (course id: %s)",  # noqa: E501
            course_module.id,
        )


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def async_create_github_repo(self, course_key_str, export_course=False):  # noqa: FBT002
    """
    Create a GitHub repository for the given course key.

    Args:
        course_key_str (str): The course key for which to create the repository.
        export_course (bool): Whether to export the course content
            after creating the repo.

    Returns:
        tuple(bool, str): A tuple containing a boolean indicating success,
            and the SSH URL of the created repository or an error message.
    """

    course_key = CourseKey.from_string(course_key_str)
    course_id_slugified = github_repo_name_format(str(course_key))

    response_msg = ""
    if CourseGitRepository.objects.filter(course_key=course_key).exists():
        response_msg = f"GitHub repository already exists for course {course_key}. Skipping creation."  # noqa: E501
        LOGGER.info(response_msg)
        return False, response_msg

    course_module = modulestore().get_course(course_key)
    url = f"{settings.GITHUB_ORG_API_URL}/repos"
    # https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.GITHUB_ACCESS_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_desc = f"{course_module.display_name}, exported from https://{settings.CMS_BASE}/course/{course_key_str}"
    payload = {
        "name": course_id_slugified,
        "description": repo_desc,
        "private": True,
        "has_issues": False,
        "has_projects": False,
        "has_wiki": False,
        "auto_init": True,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != status.HTTP_201_CREATED:
        response_msg = f"Failed to create GitHub repository for course {course_key}: {response.json()}"  # noqa: E501
        LOGGER.error(response_msg)

        # Retry the task if we haven't exceeded max retries
        max_retries = self.retry_kwargs.get("max_retries", 3)
        if self.request.retries < max_retries:
            LOGGER.info(
                "Retrying GitHub repository creation for course %s (attempt %d/%d)",
                course_key,
                self.request.retries + 1,
                max_retries,
            )
            countdown = self.retry_kwargs.get("countdown", 10)
            raise self.retry(countdown=countdown, exc=Exception(response_msg))

        return False, response_msg

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        CourseGitRepository.objects.create(
            course_key=course_key,
            git_url=ssh_url,
        )
        LOGGER.info(
            "GitHub repository created for course %s: %s",
            course_key,
            ssh_url,
        )
    else:
        response_msg = f"""
            Failed to retrieve SSH URL from GitHub response for course {course_key}.
            Response data: {repo_data}
        """
        LOGGER.error(response_msg)

    if ssh_url and export_course:
        export_course_to_git(course_key)

    return True, response_msg or ssh_url
