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
from rest_framework import status

from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.utils import (
    get_content_info,
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
        content_info = get_content_info(content_key)
    except Exception:
        LOGGER.exception("Failed to parse content key: %s", content_key_string)
        return

    try:
        content_repo = ContentGitRepository.objects.get(content_key=content_key)

        if content_repo.is_export_enabled:
            LOGGER.info(
                "Starting async %s content export to git (%s id: %s)",
                content_info["content_type"],
                content_info["content_type"],
                content_info["content_module"].id
                if hasattr(content_info["content_module"], "id")
                else content_key,
            )
            # Use unified export_to_git that handles both courses and libraries
            export_to_git(content_key, content_repo.git_url, user=user)
        else:
            LOGGER.info(
                "Git export is disabled for %s %s. Skipping export.",
                content_info["content_type"],
                content_key_string,
            )
    except GitExportError:
        LOGGER.exception(
            "Failed async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_info["content_module"].id
            if hasattr(content_info["content_module"], "id")
            else content_key,
        )
    except ContentGitRepository.DoesNotExist:
        LOGGER.exception(
            "Git repository does not exist for %s %s. "
            "Creating repository and exporting content.",
            content_info["content_type"],
            content_key_string,
        )
        if is_auto_repo_creation_enabled(is_library=content_info["is_library"]):
            async_create_github_repo.delay(str(content_key), export_content=True)
    except Exception:
        LOGGER.exception(
            "Unknown error occurred during async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_info["content_module"].id
            if hasattr(content_info["content_module"], "id")
            else content_key,
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
        content_info = get_content_info(content_key)
    except Exception:
        LOGGER.exception("Failed to parse content key: %s", content_key_str)
        return False, f"Invalid content key: {content_key_str}"

    content_id_slugified = github_repo_name_format(str(content_key))
    response_msg = ""

    # Check if repository already exists
    if ContentGitRepository.objects.filter(content_key=content_key).exists():
        response_msg = f"GitHub repository already exists for {content_info['content_type']} {content_key}. Skipping creation."  # noqa: E501
        LOGGER.info(response_msg)
        return False, response_msg

    # Determine URL path based on content type
    url_path = f"{content_info['content_type']}/{content_key_str}"

    # Get display name (v2 libraries use 'title', others use 'display_name')
    if content_info["is_v2_library"]:
        display_name = content_info["content_module"].title
    else:
        display_name = content_info["content_module"].display_name

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
        response_msg = f"Failed to create GitHub repository for {content_info['content_type']} {content_key}: {response.json()}"  # noqa: E501
        LOGGER.error(response_msg)

        # Retry the task if we haven't exceeded max retries
        max_retries = self.retry_kwargs.get("max_retries", 3)
        if self.request.retries < max_retries:
            LOGGER.info(
                "Retrying GitHub repository creation for %s %s (attempt %d/%d)",
                content_info["content_type"],
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
            content_info["content_type"],
            content_key,
            ssh_url,
        )
    else:
        response_msg = f"""
            Failed to retrieve SSH URL from GitHub response
            for {content_info["content_type"]} {content_key}.
            Response data: {repo_data}
        """
        LOGGER.error(response_msg)

    if ssh_url and export_content:
        async_export_to_git(content_key_str)

    return True, response_msg or ssh_url
