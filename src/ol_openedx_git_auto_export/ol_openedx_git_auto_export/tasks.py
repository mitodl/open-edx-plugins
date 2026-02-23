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
from opaque_keys.edx.keys import LearningContextKey
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.api import get_library
from rest_framework import status
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.utils import (
    github_repo_name_format,
    is_auto_repo_creation_enabled,
)

LOGGER = get_task_logger(__name__)


@shared_task
def async_export_to_git(content_key_string, user=None):
    """Export a course or library to Git.

    Args:
        content_key_string (str): String representation of CourseKey or LibraryLocator
        user: Optional user for git export
    """
    # Parse as LearningContextKey to support all learning contexts
    try:
        content_key = LearningContextKey.from_string(content_key_string)
        is_v1_library = isinstance(content_key, LibraryLocator)
        is_v2_library = isinstance(content_key, LibraryLocatorV2)
    except Exception:
        LOGGER.exception("Failed to parse content key: %s", content_key_string)
        return

    # Get the content module (course or library)
    if is_v2_library:
        # V2 libraries use content_libraries API
        content_module = get_library(content_key)
        content_type = "library"
    elif is_v1_library:
        # V1 libraries use modulestore
        content_module = modulestore().get_library(content_key)
        content_type = "library"
    else:
        content_module = modulestore().get_course(content_key)
        content_type = "course"

    try:
        content_repo = ContentGitRepository.objects.get(content_key=content_key)

        if content_repo.is_export_enabled:
            LOGGER.info(
                "Starting async %s content export to git (%s id: %s)",
                content_type,
                content_type,
                content_module.id if hasattr(content_module, "id") else content_key,
            )
            # Use unified export_to_git that handles both courses and libraries
            export_to_git(content_key, content_repo.git_url, user=user)
        else:
            LOGGER.info(
                "Git export is disabled for %s %s. Skipping export.",
                content_type,
                content_key_string,
            )
    except GitExportError:
        LOGGER.exception(
            "Failed async %s content export to git (%s id: %s)",
            content_type,
            content_type,
            content_module.id if hasattr(content_module, "id") else content_key,
        )
    except ContentGitRepository.DoesNotExist:
        LOGGER.exception(
            "Git repository does not exist for %s %s. "
            "Creating repository and exporting content.",
            content_type,
            content_key_string,
        )
        if is_auto_repo_creation_enabled(is_library=is_v1_library or is_v2_library):
            async_create_github_repo.delay(str(content_key), export_content=True)
    except Exception:
        LOGGER.exception(
            "Unknown error occurred during async %s content export to git (%s id: %s)",
            content_type,
            content_type,
            content_module.id if hasattr(content_module, "id") else content_key,
        )


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def async_create_github_repo(self, content_key_str, export_content=False):  # noqa: FBT002
    """
    Create a GitHub repository for the given course or library key.

    Args:
        content_key_str (str): The course/library key for which to create repository.
        export_content (bool): Whether to export the content
            after creating the repo.

    Returns:
        tuple(bool, str): A tuple containing a boolean indicating success,
            and the SSH URL of the created repository or an error message.
    """

    # Parse as LearningContextKey to support all learning contexts
    try:
        content_key = LearningContextKey.from_string(content_key_str)
        is_v1_library = isinstance(content_key, LibraryLocator)
        is_v2_library = isinstance(content_key, LibraryLocatorV2)
    except Exception:
        LOGGER.exception("Failed to parse content key: %s", content_key_str)
        return False, f"Invalid content key: {content_key_str}"

    content_type = "library" if is_v1_library or is_v2_library else "course"
    content_id_slugified = github_repo_name_format(str(content_key))

    response_msg = ""

    # Check if repository already exists
    if ContentGitRepository.objects.filter(content_key=content_key).exists():
        response_msg = f"GitHub repository already exists for {content_type} {content_key}. Skipping creation."  # noqa: E501
        LOGGER.info(response_msg)
        return False, response_msg

    # Get the content module (course or library)
    if is_v2_library:
        # V2 libraries use content_libraries API
        content_module = get_library(content_key)
        url_path = f"library/{content_key_str}"
    elif is_v1_library:
        # V1 libraries use modulestore
        content_module = modulestore().get_library(content_key)
        url_path = f"library/{content_key_str}"
    else:
        content_module = modulestore().get_course(content_key)
        url_path = f"course/{content_key_str}"

    if is_v2_library:
        display_name = content_module.title
    else:
        display_name = content_module.display_name

    url = f"{settings.GITHUB_ORG_API_URL}/repos"
    # https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {settings.GITHUB_ACCESS_TOKEN}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    repo_desc = f"{display_name}, exported from https://{settings.CMS_BASE}/{url_path}"
    payload = {
        "name": content_id_slugified,
        "description": repo_desc,
        "private": True,
        "has_issues": False,
        "has_projects": False,
        "has_wiki": False,
        "auto_init": True,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != status.HTTP_201_CREATED:
        response_msg = f"Failed to create GitHub repository for {content_type} {content_key}: {response.json()}"  # noqa: E501
        LOGGER.error(response_msg)

        # Retry the task if we haven't exceeded max retries
        max_retries = self.retry_kwargs.get("max_retries", 3)
        if self.request.retries < max_retries:
            LOGGER.info(
                "Retrying GitHub repository creation for %s %s (attempt %d/%d)",
                content_type,
                content_key,
                self.request.retries + 1,
                max_retries,
            )
            countdown = self.retry_kwargs.get("countdown", 10)
            raise self.retry(countdown=countdown, exc=Exception(response_msg))

        return False, response_msg

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        # Use the new ContentGitRepository model
        ContentGitRepository.objects.create(
            content_key=content_key,
            git_url=ssh_url,
        )
        LOGGER.info(
            "GitHub repository created for %s %s: %s",
            content_type,
            content_key,
            ssh_url,
        )
    else:
        response_msg = f"""
            Failed to retrieve SSH URL from GitHub response
            for {content_type} {content_key}.
            Response data: {repo_data}
        """
        LOGGER.error(response_msg)

    if ssh_url and export_content:
        async_export_to_git(content_key_str)

    return True, response_msg or ssh_url
