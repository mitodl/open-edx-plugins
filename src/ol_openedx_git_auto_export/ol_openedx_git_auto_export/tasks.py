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
from django.core.exceptions import ImproperlyConfigured
from opaque_keys.edx.keys import CourseKey
from rest_framework import status
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import ENABLE_AUTO_GITHUB_REPO_CREATION
from ol_openedx_git_auto_export.models import CourseGithubRepository
from ol_openedx_git_auto_export.utils import (
    export_course_to_git,
    github_repo_name_format,
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
        LOGGER.debug(
            "Starting async course content export to git (course id: %s)",
            course_module.id,
        )
        course_repo = CourseGithubRepository.objects.get(course_id=course_key_string)
        export_to_git(course_module.id, course_repo.git_url, user=user)
    except GitExportError:
        LOGGER.exception(
            "Failed async course content export to git (course id: %s)",
            course_module.id,
        )
    except CourseGithubRepository.DoesNotExist:
        LOGGER.debug(
            "CourseGithubRepository does not exist for course %s. Skipping export.",
            course_key_string,
        )
    except Exception:
        LOGGER.exception(
            "Unknown error occured during async course content export to git (course id: %s)",  # noqa: E501
            course_module.id,
        )


@shared_task
def async_create_github_repo(course_key_str, export_course=False):  # noqa: FBT002
    """
    Create a GitHub repository for the given course key.

    Args:
        course_key_str (str): The course key for which to create the repository.
        export_course (bool): Whether to export the course content
            after creating the repo.

    Returns:
        str or None: The SSH URL of the created repository, or None if creation failed.
    """

    course_key = CourseKey.from_string(course_key_str)
    course_id_slugified = github_repo_name_format(str(course_key))
    if not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION):
        LOGGER.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation for course %s",  # noqa: E501
            course_key,
        )
        return None

    if CourseGithubRepository.objects.filter(course_id=str(course_key)).exists():
        LOGGER.info(
            "GitHub repository already exists for course %s. Skipping creation.",
            course_key,
        )
        return None

    gh_access_token = settings.GITHUB_ACCESS_TOKEN
    if not settings.GITHUB_ORG_API_URL or not gh_access_token:
        error_msg = "GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set in settings. Skipping GitHub repo creation."  # noqa: E501
        raise ImproperlyConfigured(error_msg)

    course_module = modulestore().get_course(course_key)
    url = f"{settings.GITHUB_ORG_API_URL}/repos"
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {gh_access_token}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_desc = f"{course_module.display_name}, exported from {settings.CMS_BASE}"
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
        LOGGER.error(
            "Failed to create GitHub repository for course %s: %s",
            course_key,
            response.json(),
        )
        return None

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        CourseGithubRepository.objects.create(
            course_id=course_key,
            git_url=ssh_url,
        )
        LOGGER.info(
            "GitHub repository created for course %s: %s",
            course_key,
            ssh_url,
        )
    else:
        LOGGER.error(
            "Failed to retrieve SSH URL for GitHub repository for course %s",
            course_key,
        )

    if export_course:
        export_course_to_git(course_key)

    return ssh_url
