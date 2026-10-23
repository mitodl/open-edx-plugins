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

from ol_openedx_git_auto_export.constants import EXPORT_TIME_LIMIT
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError
from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.utils import (
    acquire_export_lock,
    burst_exceeded_max_wait,
    clear_stale_git_lock,
    current_export_token,
    get_content_info,
    github_repo_name_format,
    is_auto_repo_creation_enabled,
    queue_debounced_export,
    queue_export_task,
    release_export_lock,
    release_export_slot,
    schedule_export_with_debounce,
)

LOGGER = get_task_logger(__name__)


def _superseded(context_key_string, user, token):
    """
    Report whether a newer signal replaced this task, re-queuing if so.
    """
    current_token = current_export_token(context_key_string, token)
    stale = current_token != token
    if stale and burst_exceeded_max_wait(context_key_string):
        LOGGER.info(
            "Signals for %s have postponed its export too long; exporting now",
            context_key_string,
        )
        stale = False
    if not stale:
        return False

    LOGGER.info(
        "Newer signals arrived for %s; re-queuing rather than exporting "
        "a mid-burst snapshot",
        context_key_string,
    )
    try:
        # Still holding the slot, so no signal can slip a second task in. A
        # burst extended by another publisher keeps the first as author.
        queue_export_task(context_key_string, user, current_token)
    except Exception:
        # queue_export_task released the slot on its way out.
        LOGGER.exception(
            "Failed to re-queue %s; exporting current state instead",
            context_key_string,
        )
        return False

    return True


def _export_unless_unchanged(context_key, git_url, user):
    """
    Run export_to_git, treating unchanged content as success.

    export_to_git raises CANNOT_COMMIT both for this and for real failures
    such as a held index.lock; only git's own output tells them apart.
    """
    try:
        export_to_git(context_key, git_url, user=user)
    except GitExportError as exc:
        output = getattr(exc.__cause__, "output", None) or ""
        # bytes today (check_output without text=True); str if that changes.
        if isinstance(output, bytes):
            output = output.decode(errors="replace")
        if "nothing to commit" not in output:
            raise
        LOGGER.info("No changes to export for %s", context_key)


def _wait_for_running_export(context_key_string, user, token):
    """
    Re-queue behind another export of the same content.

    The running export may predate this task's changes, so this one runs
    after it instead of racing it on the same clone directory.
    """
    LOGGER.info("%s is already being exported; waiting for it", context_key_string)
    if token:
        # Keeps the slot and the burst's start, as a superseded task does.
        queue_export_task(
            context_key_string, user, current_export_token(context_key_string, token)
        )
    else:
        queue_debounced_export(context_key_string, lambda: user)


@shared_task(time_limit=EXPORT_TIME_LIMIT)
def async_export_to_git(context_key_string, user=None, token=None):
    """Export a course or library to Git.

    Args:
        context_key_string (str): String representation of LearningContextKey
        user: Optional user for git export
        token: Debounce token from utils.queue_export_task; see
            EXPORT_DEBOUNCE_CACHE_KEY in constants.py for the mechanism.
            None skips the staleness check and the debounce state, and
            exists only for messages queued by releases predating the token.
    """
    if token and _superseded(context_key_string, user, token):
        return

    owned = acquire_export_lock(context_key_string)
    if owned is False:
        _wait_for_running_export(context_key_string, user, token)
        return
    try:
        if token:
            # Release before exporting, so signals landing during the export
            # queue a fresh task instead of being dropped. Only now, holding
            # the lock: this also ends the burst, which a wait must not do.
            release_export_slot(context_key_string)
        _export(context_key_string, user)
    finally:
        # None means the cache was down: this export never held the lock.
        if owned:
            release_export_lock(context_key_string)


def _export(context_key_string, user):
    """Resolve the content and its repository, then export it."""
    try:
        context_key = LearningContextKey.from_string(context_key_string)
        content_info = get_content_info(context_key)
    except ContentNotFoundError:
        # Publishes queue from on_commit and on-demand exports write nothing, so
        # not the old pre-commit race: the content was most likely deleted
        # during the countdown. Nothing re-queues.
        LOGGER.warning(
            "Content %s not found; abandoning this export (no retry)",
            context_key_string,
        )
        return
    except Exception:
        # Also covers get_content_info's lookups, so not necessarily a bad key.
        LOGGER.exception("Failed to resolve content %s", context_key_string)
        raise

    try:
        content_repo = ContentGitRepository.objects.get(content_key=context_key)

        if content_repo.is_export_enabled:
            LOGGER.info(
                "Starting async %s content export to git (%s id: %s)",
                content_info["content_type"],
                content_info["content_type"],
                content_info["content_module"].id
                if hasattr(content_info["content_module"], "id")
                else context_key,
            )
            # Remove any stale .git/index.lock left by a previously crashed worker.
            # Dirty working-tree files from a prior crash are cleaned by the
            # `git reset --hard origin/<branch>` + `git clean` inside export_to_git.
            clear_stale_git_lock(content_repo.git_url)
            _export_unless_unchanged(context_key, content_repo.git_url, user)
        else:
            LOGGER.info(
                "Git export is disabled for %s %s. Skipping export.",
                content_info["content_type"],
                context_key_string,
            )
    except GitExportError:
        LOGGER.exception(
            "Failed async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_info["content_module"].id
            if hasattr(content_info["content_module"], "id")
            else context_key,
        )
        # Re-raised, not retried, so Celery records the failure; a retry
        # would hit the same push or commit error.
        raise
    except ContentGitRepository.DoesNotExist:
        LOGGER.info(
            "No git repository registered for %s %s; "
            "creating one if auto-creation is enabled.",
            content_info["content_type"],
            context_key_string,
        )
        try:
            if is_auto_repo_creation_enabled(is_library=content_info["is_library"]):
                async_create_github_repo.delay(str(context_key), export_content=True)
        except Exception:
            # Sibling except clauses don't catch this one.
            LOGGER.exception(
                "Failed to check/trigger repo creation for %s %s",
                content_info["content_type"],
                context_key_string,
            )
    except Exception:
        LOGGER.exception(
            "Unknown error occurred during async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_info["content_module"].id
            if hasattr(content_info["content_module"], "id")
            else context_key,
        )
        raise


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def async_create_github_repo(self, context_key_str, export_content=False):  # noqa: FBT002
    """
    Create a GitHub repository for the given course or library key.

    Args:
        context_key_str (str): The course/library key for which to create repository.
        export_content (bool): Whether to export the content
            after creating the repo.

    Returns:
        tuple(bool, str): A tuple containing a boolean indicating success,
            and the SSH URL of the created repository or an error message.
    """

    # Parse as LearningContextKey to support all learning contexts
    try:
        context_key = LearningContextKey.from_string(context_key_str)
        content_info = get_content_info(context_key)
    except ContentNotFoundError as exc:
        response_msg = f"Content {context_key_str} not found: {exc}"
        LOGGER.warning(response_msg)
        return False, response_msg
    except Exception:
        LOGGER.exception("Failed to parse context key: %s", context_key_str)
        return False, f"Invalid context key: {context_key_str}"

    content_id_slugified = github_repo_name_format(str(context_key))
    response_msg = ""

    # Check if repository already exists
    if ContentGitRepository.objects.filter(content_key=context_key).exists():
        response_msg = f"GitHub repository already exists for {content_info['content_type']} {context_key}. Skipping creation."  # noqa: E501
        LOGGER.info(response_msg)
        return False, response_msg

    # Determine URL path based on content type
    url_path = (
        f"{settings.GIT_AUTO_EXPORT_AUTHORING_URL_PREFIX}"
        f"/{content_info['content_type']}/{context_key_str}"
    )

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
        response_msg = f"Failed to create GitHub repository for {content_info['content_type']} {context_key}: {response.json()}"  # noqa: E501
        LOGGER.error(response_msg)

        # Retry the task if we haven't exceeded max retries
        max_retries = self.retry_kwargs.get("max_retries", 3)
        if self.request.retries < max_retries:
            LOGGER.info(
                "Retrying GitHub repository creation for %s %s (attempt %d/%d)",
                content_info["content_type"],
                context_key,
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
            content_key=context_key,
            git_url=ssh_url,
        )
        LOGGER.info(
            "GitHub repository created for %s %s: %s",
            content_info["content_type"],
            context_key,
            ssh_url,
        )
    else:
        response_msg = f"""
            Failed to retrieve SSH URL from GitHub response
            for {content_info["content_type"]} {context_key}.
            Response data: {repo_data}
        """
        LOGGER.error(response_msg)

    if ssh_url and export_content:
        # Debounced like every other export, so it coalesces with an import
        # burst instead of racing it on the same clone directory. No author.
        schedule_export_with_debounce(context_key, lambda: None)

    return True, response_msg or ssh_url
