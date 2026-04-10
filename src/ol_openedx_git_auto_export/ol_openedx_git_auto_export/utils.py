"""
Utility functions for the ol_openedx_git_auto_export app.
"""

import logging
import os
import re
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    EXPORT_LOCK_CACHE_KEY,
    EXPORT_LOCK_MAX_RETRIES,
    EXPORT_LOCK_RETRY_DELAY,
    EXPORT_LOCK_TIMEOUT,
    EXPORT_PENDING_CACHE_KEY,
    EXPORT_PENDING_TIMEOUT,
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


def clear_stale_git_lock(git_url):
    """
    Remove a stale .git/index.lock file for the local clone of git_url, if present.

    This must only be called after acquiring the per-course distributed cache lock,
    which guarantees no other process is running git operations on the same directory.
    A stale lock file is left behind when a worker process is killed mid-operation.
    """
    git_repo_export_dir = getattr(
        settings, "GIT_REPO_EXPORT_DIR", "/openedx/export_course_repos"
    )
    rdir = git_url.rsplit("/", 1)[-1].rsplit(".git", 1)[0]
    index_lock = Path(git_repo_export_dir) / rdir / ".git" / "index.lock"
    if index_lock.exists():
        log.warning(
            "Removing stale .git/index.lock for repo %s at %s", git_url, index_lock
        )
        index_lock.unlink()


def acquire_export_lock_or_schedule(task, course_key_string):
    """
    Attempt to acquire the per-course git-export distributed lock.

    Uses two cache keys:
    - ``EXPORT_LOCK_CACHE_KEY``    — held while the export is running.
    - ``EXPORT_PENDING_CACHE_KEY`` — stores the task-ID of the single task
      that is waiting to run after the lock-holder finishes.

    Returns True if the caller acquired the lock and should proceed with the
    export.  Returns False if the caller is a duplicate that was dropped.
    Raises ``celery.exceptions.Retry`` if the caller is the designated pending
    task and needs to retry later.
    """
    lock_key = EXPORT_LOCK_CACHE_KEY.format(course_key=course_key_string)
    pending_key = EXPORT_PENDING_CACHE_KEY.format(course_key=course_key_string)
    task_id = task.request.id

    if not cache.add(lock_key, task_id, timeout=EXPORT_LOCK_TIMEOUT):
        # Lock is held — check if we are already the designated pending task.
        if cache.get(pending_key) == task_id:
            log.info(
                "Export lock still held for %s, pending task %s retrying in %ds"
                " (attempt %d/%d)",
                course_key_string,
                task_id,
                EXPORT_LOCK_RETRY_DELAY,
                task.request.retries + 1,
                EXPORT_LOCK_MAX_RETRIES,
            )
            raise task.retry(
                countdown=EXPORT_LOCK_RETRY_DELAY, max_retries=EXPORT_LOCK_MAX_RETRIES
            )

        # Try to become the single designated pending task (atomic).
        if cache.add(pending_key, task_id, timeout=EXPORT_PENDING_TIMEOUT):
            log.info(
                "Export already in progress for %s; task %s queued as pending,"
                " retrying in %ds",
                course_key_string,
                task_id,
                EXPORT_LOCK_RETRY_DELAY,
            )
            raise task.retry(
                countdown=EXPORT_LOCK_RETRY_DELAY, max_retries=EXPORT_LOCK_MAX_RETRIES
            )

        # Pending slot already taken — drop this duplicate.
        log.info(
            "Dropping duplicate export task %s for %s (lock held, pending slot taken)",
            task_id,
            course_key_string,
        )
        return False

    # Lock acquired — clear the pending slot so a fresh task can claim it.
    cache.delete(pending_key)
    return True


def release_export_lock(course_key_string):
    """
    Release the per-course git-export distributed lock.

    Must be called in a ``finally`` block after ``acquire_export_lock_or_schedule``
    returns True.
    """
    cache.delete(EXPORT_LOCK_CACHE_KEY.format(course_key=course_key_string))


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
