"""
Utility functions for the ol_openedx_git_auto_export app.
"""

import logging
import os

import requests
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    REPOSITORY_NAME_MAX_LENGTH,
)
from ol_openedx_git_auto_export.models import CourseGitRepo
from ol_openedx_git_auto_export.tasks import async_export_to_git

log = logging.getLogger(__name__)


def get_publisher_username(course_module):
    """
    Return the username of the user who published the course.
    If the user cannot be found, returns None.
    """
    if not course_module:
        return None

    user_id = getattr(course_module, "published_by", None)
    if not user_id:
        return None

    user = User.objects.filter(id=user_id).first()
    return user.username if user else None


def get_or_create_git_export_repo_dir():
    git_repo_export_dir = getattr(
        settings, "GIT_REPO_EXPORT_DIR", "/openedx/export_course_repos"
    )
    if not os.path.exists(git_repo_export_dir):  # noqa: PTH110
        # for development/docker/vagrant if GIT_REPO_EXPORT_DIR folder does not exist then create it  # noqa: E501
        log.error(
            "GIT_REPO_EXPORT_DIR is not available in settings, please create it first"
        )
        os.makedirs(git_repo_export_dir, 0o755)  # noqa: PTH103

    return git_repo_export_dir


def github_repo_name_format(course_id_str):
    """
    Format course ID to comply with GitHub repository naming conventions using slugify.

    GitHub repository names:
    - Can only contain alphanumeric characters
    - And hyphens (-), underscores (_), and periods (.)
    - Cannot start or end with a hyphen
    - Maximum length is 100 characters

    Args:
        course_id_str (str): The course ID string to format

    Returns:
        str: GitHub-compliant repository name
    """
    # Replace all characters with - hyphen except alphanumeric, hyphen, underscore, and period  # noqa: E501
    repo_name = "".join(
        char if char.isalnum() or char in "-_." else "-" for char in course_id_str
    ).strip("-")

    # Truncate to 100 characters if needed
    if len(repo_name) > REPOSITORY_NAME_MAX_LENGTH:
        repo_name = repo_name[:REPOSITORY_NAME_MAX_LENGTH].rstrip("-")

    return repo_name.replace("course-v1-", "")


def create_github_repo(course_key):
    """Create a GitHub repository for the given course key.
    Args:
        course_key (CourseKey): The course key for which to create the repository.
    Returns:
        str or None: The SSH URL of the created repository, or None if creation failed.
    """

    course_id_slugified = github_repo_name_format(str(course_key))
    if not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION):
        log.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation for course %s",  # noqa: E501
            course_key,
        )
        return None

    # SignalHandler.course_published is called before COURSE_CREATED signal
    if CourseGitRepo.objects.filter(course_id=str(course_key)).exists():
        log.info(
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
        "has_project": False,
        "has_wiki": False,
        "auto_init": True,
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    if response.status_code != 201:  # noqa: PLR2004
        log.error(
            "Failed to create GitHub repository for course %s: %s",
            course_key,
            response.json(),
        )
        return None

    repo_data = response.json()
    ssh_url = repo_data.get("ssh_url")
    if ssh_url:
        CourseGitRepo.objects.create(
            course_id=str(course_key),
            git_url=ssh_url,
        )
        log.info(
            "GitHub repository created for course %s: %s",
            course_key,
            ssh_url,
        )
    else:
        log.error(
            "Failed to retrieve SSH URL for GitHub repository for course %s",
            course_key,
        )

    return ssh_url


def export_course_to_git(course_key):
    """
    Export the course to a Git repository.

    Args:
        course_key (CourseKey): The course key to export.
    """
    if settings.FEATURES.get("ENABLE_EXPORT_GIT") and settings.FEATURES.get(
        ENABLE_GIT_AUTO_EXPORT
    ):
        get_or_create_git_export_repo_dir()
        course_module = modulestore().get_course(course_key)
        log.info(
            "Course published with auto-export enabled. Starting export... (course id: %s)",  # noqa: E501
            course_key,
        )

        user = get_publisher_username(course_module)
        async_export_to_git.delay(str(course_key), user)
