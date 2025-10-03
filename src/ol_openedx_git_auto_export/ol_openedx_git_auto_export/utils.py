"""
Utility functions for the ol_openedx_git_auto_export app.
"""

import logging
import os
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    REPOSITORY_NAME_MAX_LENGTH,
)

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
    """
    Ensure the git export directory exists and return its path.
    """
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


def github_repo_name_format(course_key_str):
    """
    Format course ID to comply with GitHub repository naming conventions using slugify.

    GitHub repository names:
    - Can only contain alphanumeric characters
    - And hyphens (-), underscores (_), and periods (.)
    - Cannot start or end with a hyphen
    - Maximum length is 100 characters

    Args:
        course_key_str (str): The course key string to format

    Returns:
        str: GitHub-compliant repository name
    """
    # Replace all characters with - hyphen except alphanumeric, hyphen, underscore, and period  # noqa: E501
    repo_name = re.sub(r"[^A-Za-z0-9_.-]", "-", course_key_str).strip("-")

    # Truncate to 100 characters if needed
    # Take the last characters to preserve course run identifier
    if len(repo_name) > REPOSITORY_NAME_MAX_LENGTH:
        repo_name = repo_name[-REPOSITORY_NAME_MAX_LENGTH:].lstrip("-")

    return repo_name.replace("course-v1-", "")


def export_course_to_git(course_key):
    """
    Export the course to a Git repository.

    Args:
        course_key (CourseKey): The course key of the course to export.
    """
    from ol_openedx_git_auto_export.tasks import async_export_to_git  # noqa: PLC0415

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


def is_auto_repo_creation_enabled():
    """
    Check if automatic GitHub repository creation is enabled.

    Args:
        course_key (CourseKey): The course key of the course to check.

    Returns:
        bool: True if automatic GitHub repository creation is enabled, False otherwise.

    Raises:
        ImproperlyConfigured: If GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set.
    """
    if not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION):
        log.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation ...",
        )
        return False

    if not (settings.GITHUB_ORG_API_URL and settings.GITHUB_ACCESS_TOKEN):
        error_msg = "GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set in settings. Skipping GitHub repo creation."  # noqa: E501
        raise ImproperlyConfigured(error_msg)

    return True
