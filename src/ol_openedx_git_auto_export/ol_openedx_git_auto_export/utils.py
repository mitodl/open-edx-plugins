"""
Utility functions for the ol_openedx_git_auto_export app.
"""

import logging
import os
import re

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ImproperlyConfigured
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.api import get_library
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION,
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    ENABLE_GIT_AUTO_LIBRARY_EXPORT,
    REPOSITORY_NAME_MAX_LENGTH,
    ContentType,
)

log = logging.getLogger(__name__)


def get_content_info(content_key):
    """
    Get information about a content item (course or library).

    Args:
        content_key: A LearningContextKey

    Returns:
        dict: Dictionary containing:
            - content_type: The ContentType enum value (str)
            - content_module: The actual course/library object
            - is_v1_library: Boolean flag
            - is_v2_library: Boolean flag
            - is_library: Boolean flag (True if v1 or v2 library)
    """
    is_v1_library = isinstance(content_key, LibraryLocator)
    is_v2_library = isinstance(content_key, LibraryLocatorV2)

    # Get the content module based on type
    if is_v2_library:
        # V2 libraries use content_libraries API
        content_module = get_library(content_key)
        content_type = ContentType.LIBRARY.value
    elif is_v1_library:
        # V1 libraries use modulestore
        content_module = modulestore().get_library(content_key)
        content_type = ContentType.LIBRARY.value
    else:
        # Courses use modulestore
        content_module = modulestore().get_course(content_key)
        content_type = ContentType.COURSE.value

    return {
        "content_type": content_type,
        "content_module": content_module,
        "is_v1_library": is_v1_library,
        "is_v2_library": is_v2_library,
        "is_library": is_v1_library or is_v2_library,
    }


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

    if is_auto_export_enabled():
        get_or_create_git_export_repo_dir()
        course_module = modulestore().get_course(course_key)
        log.info(
            "Course published with auto-export enabled. Starting export... (course id: %s)",  # noqa: E501
            course_key,
        )

        user = get_publisher_username(course_module)
        async_export_to_git.delay(str(course_key), user)


def export_library_to_git(library_key):
    """
    Export the library to a Git repository.

    Args:
        library_key (LibraryLocator | LibraryLocatorV2): The library key to export.
    """
    from ol_openedx_git_auto_export.tasks import async_export_to_git  # noqa: PLC0415

    if is_auto_export_enabled(is_library=True):
        get_or_create_git_export_repo_dir()
        log.info(
            "Library updated with auto-export enabled. Starting export... (library id: %s)",  # noqa: E501
            library_key,
        )

        # Get publisher username
        user = None
        if isinstance(library_key, LibraryLocatorV2):
            # V2 libraries have published_by in their metadata
            library_metadata = get_library(library_key)
            user = (
                library_metadata.published_by if library_metadata.published_by else None
            )
        else:
            # V1 libraries don't have published_by field
            pass

        async_export_to_git.delay(str(library_key), user=user)
    else:
        log.info(
            "Library auto-export is disabled. Skipping export for library: %s",
            library_key,
        )


def is_auto_export_enabled(is_library=False):  # noqa: FBT002
    git_export_enabled = settings.FEATURES.get("ENABLE_EXPORT_GIT")
    if is_library:
        return git_export_enabled and settings.FEATURES.get(
            ENABLE_GIT_AUTO_LIBRARY_EXPORT, False
        )

    return git_export_enabled and settings.FEATURES.get(ENABLE_GIT_AUTO_EXPORT, False)


def is_auto_repo_creation_enabled(is_library=False):  # noqa: FBT002
    """
    Check if automatic GitHub repository creation is enabled.

    Args:
        is_library (bool): Whether checking for library (True) or course (False).

    Returns:
        bool: True if automatic GitHub repository creation is enabled, False otherwise.

    Raises:
        ImproperlyConfigured: If GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set.
    """
    # Check library-specific flag first if it's a library
    if is_library:
        library_repo_enabled = settings.FEATURES.get(
            ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION, False
        )
        if not library_repo_enabled:
            log.info(
                "GitHub library repo creation is disabled. "
                "Skipping library repo creation ...",
            )
            return False
    elif not settings.FEATURES.get(ENABLE_AUTO_GITHUB_REPO_CREATION, False):
        log.info(
            "GitHub repo creation is disabled. Skipping GitHub repo creation ...",
        )
        return False

    if not (settings.GITHUB_ORG_API_URL and settings.GITHUB_ACCESS_TOKEN):
        error_msg = "GITHUB_ORG_API_URL or GITHUB_ACCESS_TOKEN is not set in settings. Skipping GitHub repo creation."  # noqa: E501
        raise ImproperlyConfigured(error_msg)

    return True
