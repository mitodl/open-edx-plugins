"""
Utility functions for the ol_openedx_git_auto_export app.
"""

import logging
import os
import re
import uuid
from functools import partial
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.api import (
    ContentLibraryNotFound,
    get_library,
)
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.constants import (
    ENABLE_AUTO_GITHUB_LIBRARY_REPO_CREATION,
    ENABLE_AUTO_GITHUB_REPO_CREATION,
    ENABLE_GIT_AUTO_EXPORT,
    ENABLE_GIT_AUTO_LIBRARY_EXPORT,
    EXPORT_DEBOUNCE_CACHE_KEY,
    EXPORT_DEBOUNCE_DELAY,
    EXPORT_DEBOUNCE_PENDING_CACHE_KEY,
    EXPORT_DEBOUNCE_PENDING_TTL,
    REPOSITORY_NAME_MAX_LENGTH,
    ContentType,
)
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError

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

    Raises:
        ContentNotFoundError: If the course/library isn't found.
    """
    is_v1_library = isinstance(content_key, LibraryLocator)
    is_v2_library = isinstance(content_key, LibraryLocatorV2)

    # Get the content module based on type
    if is_v2_library:
        # V2 libraries use content_libraries API, which raises
        # ContentLibraryNotFound (a DoesNotExist alias) rather than
        # returning None.
        try:
            content_module = get_library(content_key)
        except ContentLibraryNotFound as exc:
            msg = f"Library {content_key} not found via content_libraries API."
            raise ContentNotFoundError(msg) from exc
        content_type = ContentType.LIBRARY.value
    elif is_v1_library:
        content_module = modulestore().get_library(content_key)
        content_type = ContentType.LIBRARY.value
        if content_module is None:
            msg = f"Library {content_key} not found in modulestore."
            raise ContentNotFoundError(msg)
    else:
        content_module = modulestore().get_course(content_key)
        content_type = ContentType.COURSE.value
        if content_module is None:
            msg = f"Course {content_key} not found in modulestore."
            raise ContentNotFoundError(msg)

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


def debounce_cache_key(content_key):
    """Cache key holding the debounce token; see EXPORT_DEBOUNCE_CACHE_KEY."""
    return EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=str(content_key))


def pending_cache_key(content_key):
    """Cache key marking that an export task is already queued for this content."""
    return EXPORT_DEBOUNCE_PENDING_CACHE_KEY.format(content_key=str(content_key))


def cache_op(op, *args, on_error=None, **kwargs):
    """
    Run a debounce cache operation, returning on_error if the backend is down.

    Callers pick an on_error that keeps the export happening: exporting twice
    is recoverable, never exporting is not.
    """
    try:
        return op(*args, **kwargs)
    except Exception:
        log.exception("Git export debounce cache unavailable; failing open")
        return on_error


def claim_export_slot(content_key):
    """Claim the right to queue the next export task, if nothing holds it."""
    return cache_op(
        cache.add,
        pending_cache_key(content_key),
        "1",
        timeout=EXPORT_DEBOUNCE_PENDING_TTL,
        on_error=True,
    )


def release_export_slot(content_key):
    """
    Give up the slot so the next signal queues a task.

    The slot outlives whatever failed while holding it, so without this the
    burst goes unexported until the marker expires.
    """
    cache_op(cache.delete, pending_cache_key(content_key))


def queue_export_task(content_key, user, token):
    """
    Queue an export task. The caller must hold the slot from claim_export_slot.

    Args:
        content_key: The course or library key to export.
        user: Optional publisher username for the git commit.
        token: Debounce token the task must still match in order to export.
    """
    from ol_openedx_git_auto_export.tasks import async_export_to_git  # noqa: PLC0415

    log.info("Queuing git export for %s in %ds", content_key, EXPORT_DEBOUNCE_DELAY)
    try:
        async_export_to_git.apply_async(
            args=[str(content_key), user],
            kwargs={"token": token},
            countdown=EXPORT_DEBOUNCE_DELAY,
        )
    except Exception:
        release_export_slot(content_key)
        raise


def _schedule_export_with_debounce(content_key, resolve_user):
    """
    Schedule a git export task, debouncing bursts of signals for the same content.

    See EXPORT_DEBOUNCE_CACHE_KEY in constants.py for the mechanism.

    Args:
        content_key: The course or library key to export.
        resolve_user: Callable returning the publisher username. Called only
            for the signal that queues the task, since it costs several
            queries and the rest of the burst would discard the result.
    """
    # Studio publishes under ATOMIC_REQUESTS, so a task queued now can wake
    # before the content it exports is visible to the worker and give up
    # without retrying. Waiting for the commit also means an import's signals
    # are debounced against each other rather than against the commit.
    # robust=True: Django runs on_commit callbacks for one transaction in a
    # single loop and stops at the first one that raises, so a failure here
    # would otherwise silently cancel every later signal's callback too.
    transaction.on_commit(
        partial(_queue_debounced_export, content_key, resolve_user), robust=True
    )


def _queue_debounced_export(content_key, resolve_user):
    """Record this signal's token and queue a task if none is queued already."""
    token = uuid.uuid4().hex
    # Never expires: one short string per published course or library.
    cache_op(cache.set, debounce_cache_key(content_key), token, timeout=None)

    if not claim_export_slot(content_key):
        log.info(
            "Git export already queued for %s, only updating the debounce token",
            content_key,
        )
        return

    try:
        get_or_create_git_export_repo_dir()
    except Exception:
        release_export_slot(content_key)
        raise

    try:
        user = resolve_user()
    except Exception:
        # Signals that arrived while this one held the slot found it taken and
        # queued nothing, so giving up here would strand their changes. Export
        # without an author instead.
        log.exception("Exporting %s without a publisher", content_key)
        user = None

    queue_export_task(content_key, user, token)


def export_course_to_git(course_key):
    """
    Export the course to a Git repository.

    Args:
        course_key (CourseKey): The course key of the course to export.
    """
    if is_auto_export_enabled():
        log.info(
            "Course published with auto-export enabled. Starting export... (course id: %s)",  # noqa: E501
            course_key,
        )
        _schedule_export_with_debounce(
            course_key,
            lambda: get_publisher_username(modulestore().get_course(course_key)),
        )


def clear_stale_git_lock(git_url):
    """
    Remove a stale .git/index.lock file for the local clone of git_url, if present.

    A stale lock file can be left behind when a worker process is killed mid-operation.
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


def get_library_publisher(library_key):
    """
    Return the username that published the library, or None.

    V1 libraries don't have a published_by field.
    """
    if not isinstance(library_key, LibraryLocatorV2):
        return None
    try:
        return get_library(library_key).published_by or None
    except ContentLibraryNotFound:
        # The publish request can beat the library row becoming visible. Only
        # the author is lost; the task re-resolves the library when it runs.
        log.warning("Library %s not found; exporting without a publisher", library_key)
        return None


def export_library_to_git(library_key):
    """
    Export the library to a Git repository.

    Args:
        library_key (LibraryLocator | LibraryLocatorV2): The library key to export.
    """
    if is_auto_export_enabled(is_library=True):
        log.info(
            "Library updated with auto-export enabled. Starting export... (library id: %s)",  # noqa: E501
            library_key,
        )
        _schedule_export_with_debounce(
            library_key, lambda: get_library_publisher(library_key)
        )
    else:
        log.info(
            "Library auto-export is disabled. Skipping export for library: %s",
            library_key,
        )


def is_auto_export_enabled(is_library=False):  # noqa: FBT002
    """
    Check if automatic Git export is enabled.

    Args:
        is_library (bool): Whether checking for library (True) or course (False).

    Returns:
        bool: True if automatic Git export is enabled, False otherwise.
    """
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
