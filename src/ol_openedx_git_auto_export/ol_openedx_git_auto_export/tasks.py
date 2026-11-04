"""
Celery tasks for asynchronous git export operations.

This module defines background tasks that handle the actual export of course
content to Git repositories using Celery for asynchronous processing.
"""

from contextlib import contextmanager

import requests
from celery import shared_task  # pylint: disable=import-error
from celery.utils.log import get_task_logger
from cms.djangoapps.contentstore import git_export_utils
from cms.djangoapps.contentstore.git_export_utils import GitExportError, export_to_git
from django.conf import settings
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import LearningContextKey
from rest_framework import status

from ol_openedx_git_auto_export.constants import EXPORT_TIME_LIMIT
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError
from ol_openedx_git_auto_export.models import ContentGitRepository, ExportStatus
from ol_openedx_git_auto_export.utils import (
    acquire_export_lock,
    burst_exceeded_max_wait,
    claim_export_slot,
    clear_stale_git_lock,
    current_export_token,
    get_content_info,
    get_oversized_assets,
    github_repo_name_format,
    is_auto_repo_creation_enabled,
    queue_debounced_export,
    queue_export_task,
    record_export_result,
    release_export_lock,
    release_export_slot,
    schedule_export_with_debounce,
    track_export,
)

LOGGER = get_task_logger(__name__)


def _superseded(context_key_string, user, token):
    """
    Report whether a newer signal replaced this task, re-queuing if so,
    unless the burst has already waited past EXPORT_MAX_WAIT.
    """
    current_token = current_export_token(context_key_string, token)
    if current_token == token:
        return False
    if burst_exceeded_max_wait(context_key_string):
        LOGGER.info(
            "Signals for %s have postponed its export too long; exporting now",
            context_key_string,
        )
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
        # queue_export_task released the slot and burst start on its way out.
        # Re-claim them before carrying on as their owner; if a newer signal
        # got there first, its task covers this export.
        if not claim_export_slot(context_key_string):
            LOGGER.exception(
                "Failed to re-queue %s; a newer task will export it",
                context_key_string,
            )
            return True
        LOGGER.exception(
            "Failed to re-queue %s; trying to export current state instead",
            context_key_string,
        )
        return False

    return True


# export_to_git's steps, by the module-level name it calls them through.
# Releases before Willow have only cmd_log and export_course_to_xml.
_EXPORT_STEPS = {
    # The args may hold the URL, so only "git <command>".
    "cmd_log": lambda cmd, *_: f"Running {' '.join(cmd[:2])}",
    **dict.fromkeys(
        (
            "export_course_to_xml",
            "export_library_to_xml",
            "extract_library_v2_zip_to_dir",
        ),
        lambda *_: "Exporting the content",
    ),
}


def _logged(func, describe):
    def step(*args, **kwargs):
        LOGGER.info(describe(*args))
        return func(*args, **kwargs)

    return step


@contextmanager
def _log_export_steps():
    """
    Log each step export_to_git takes as it starts.

    Upstream logs git commands only after they end, at DEBUG, and the content
    export only if it fails, so a run killed mid-push or mid-export would
    show an earlier step as its last.
    """
    originals = {
        name: getattr(git_export_utils, name)
        for name in _EXPORT_STEPS
        if hasattr(git_export_utils, name)
    }
    # shortcut: patches the module for the whole process, fine for prefork
    # workers (one task per process); a pool running tasks concurrently in
    # one process would need a lock.
    for name, original in originals.items():
        setattr(git_export_utils, name, _logged(original, _EXPORT_STEPS[name]))
    try:
        yield
    finally:
        for name, original in originals.items():
            setattr(git_export_utils, name, original)


def _git_output(exc):
    """Return git's own output from a GitExportError, or ''."""
    output = getattr(exc.__cause__, "output", None) or ""
    # bytes today (check_output without text=True); str if that changes.
    if isinstance(output, bytes):
        output = output.decode(errors="replace")
    return output


def _export_unless_unchanged(context_key, git_url, user):
    """
    Run export_to_git, treating unchanged content as success.

    export_to_git raises CANNOT_COMMIT both for this and for real failures
    such as a held index.lock; only git's own output tells them apart.

    Returns False if there was nothing to commit, else True.
    """
    try:
        export_to_git(context_key, git_url, user=user)
    except GitExportError as exc:
        if "nothing to commit" not in _git_output(exc):
            raise
        LOGGER.info("No changes to export for %s", context_key)
        return False
    return True


def _wait_to_export(context_key_string, user, token):
    """
    Queue one more hop, to retry once the clone directory is free.

    Whatever holds it may predate this task's changes, so this one runs
    after it instead of racing it.
    """
    try:
        if token:
            # Keeps the slot and the burst's start, as a superseded task does.
            queue_export_task(
                context_key_string,
                user,
                current_export_token(context_key_string, token),
            )
        else:
            queue_debounced_export(context_key_string, lambda: user)
    except Exception as exc:
        # The export is lost: nothing else is queued to run it.
        record_export_result(
            context_key_string,
            ExportStatus.FAILED,
            user=user,
            error_message=f"Failed to re-queue the export: {exc!r}",
            exc=exc,
        )
        raise


def _get_content_repo(context_key_string):
    """Return the content's registered repository, or None."""
    try:
        context_key = LearningContextKey.from_string(context_key_string)
    except InvalidKeyError:
        return None  # _export reports it
    return ContentGitRepository.objects.filter(content_key=context_key).first()


def _index_unlocked(content_repo):
    """Clear a stale index.lock; False if a younger one would block git."""
    if content_repo is None or not content_repo.is_export_enabled:
        return True
    return clear_stale_git_lock(content_repo.git_url)


@shared_task(time_limit=EXPORT_TIME_LIMIT)
def async_export_to_git(context_key_string, user=None, token=None):
    """Export a course or library to Git.

    Args:
        context_key_string (str): String representation of LearningContextKey
        user: Optional user for git export
        token: Debounce token from utils.queue_export_task; see
            EXPORT_DEBOUNCE_CACHE_KEY in constants.py for the mechanism.
            None skips the staleness check, and a task that must wait
            re-enters through queue_debounced_export. It exists only for
            messages queued by releases predating the token.
    """
    if token and _superseded(context_key_string, user, token):
        return

    owned = acquire_export_lock(context_key_string)
    if owned is False:
        LOGGER.info("%s is already being exported; waiting for it", context_key_string)
        _wait_to_export(context_key_string, user, token)
        return
    try:
        try:
            content_repo = _get_content_repo(context_key_string)
            unlocked = _index_unlocked(content_repo)
        except Exception as exc:
            # Still holding the slot: later signals would see an export
            # queued that will never run.
            if token:
                release_export_slot(context_key_string)
            record_export_result(
                context_key_string,
                ExportStatus.FAILED,
                user=user,
                exc=exc,
            )
            raise
        if not unlocked:
            # A killed export's lock, or Studio's own export running.
            LOGGER.info(
                "%s has a recent index.lock; waiting for it", context_key_string
            )
            _wait_to_export(context_key_string, user, token)
            return
        if token:
            # Release before exporting, so signals landing during the export
            # queue a fresh task instead of being dropped. Only now, holding
            # the lock: this also ends the burst, which a wait must not do.
            release_export_slot(context_key_string)
        with (
            track_export(
                context_key_string,
                user,
                LOGGER,
                git_export_utils.log,
                git_url=content_repo.git_url if content_repo else "",
            ),
            _log_export_steps(),
        ):
            _export(context_key_string, user, content_repo)
    finally:
        # None means the cache was down: this export never held the lock.
        if owned:
            release_export_lock(context_key_string)


def _oversized_message(oversized):
    """Describe the assets that keep content from being exported."""
    files = ", ".join(f"{name} ({size / 2**20:.1f} MB)" for name, size in oversized)
    limit = settings.GIT_AUTO_EXPORT_MAX_FILE_SIZE / 2**20
    return (
        f"Not exported: {len(oversized)} file(s) exceed the {limit:.0f} MB "
        f"limit git hosts accept: {files}"
    )


def _export(context_key_string, user, content_repo):  # noqa: C901
    """Resolve the content, then export it to content_repo."""
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
        record_export_result(context_key_string, ExportStatus.NOT_FOUND, user=user)
        return
    except Exception as exc:
        # Also covers get_content_info's lookups, so not necessarily a bad key.
        LOGGER.exception("Failed to resolve content %s", context_key_string)
        if not isinstance(exc, InvalidKeyError):  # unstorable key: log only
            record_export_result(
                context_key_string,
                ExportStatus.FAILED,
                user=user,
                exc=exc,
            )
        raise

    if content_repo is None:
        LOGGER.info(
            "No git repository registered for %s %s; "
            "creating one if auto-creation is enabled.",
            content_info["content_type"],
            context_key_string,
        )
        note = "Auto-creation is disabled."
        queue_error = None
        try:
            if is_auto_repo_creation_enabled(is_library=content_info["is_library"]):
                async_create_github_repo.delay(str(context_key), export_content=True)
                note = "Repository creation queued."
        except Exception as exc:
            # Nothing else catches this one, and it must not fail the task.
            LOGGER.exception(
                "Failed to check/trigger repo creation for %s %s",
                content_info["content_type"],
                context_key_string,
            )
            note = f"Failed to queue repository creation: {exc!r}"
            queue_error = exc
        record_export_result(
            context_key,
            ExportStatus.NO_REPO,
            user=user,
            error_message=note,
            exc=queue_error,
        )
        return

    git_url = content_repo.git_url
    content_id = (
        content_info["content_module"].id
        if hasattr(content_info["content_module"], "id")
        else context_key
    )
    try:
        if content_repo.is_export_enabled:
            if oversized := get_oversized_assets(context_key):
                # Not raised: it recurs on every publish until the files move.
                message = _oversized_message(oversized)
                LOGGER.warning("%s: %s", context_key_string, message)
                record_export_result(
                    context_key,
                    ExportStatus.SKIPPED_LARGE_FILES,
                    user=user,
                    git_url=git_url,
                    error_message=message,
                )
                return
            LOGGER.info(
                "Starting async %s content export to git (%s id: %s)",
                content_info["content_type"],
                content_info["content_type"],
                content_id,
            )
            # _index_unlocked removed any stale index.lock; export_to_git's
            # `git reset --hard` + `git clean` handle files a crash left dirty.
            outcome = (
                ExportStatus.SUCCESS
                if _export_unless_unchanged(context_key, git_url, user)
                else ExportStatus.NO_CHANGES
            )
        else:
            LOGGER.info(
                "Git export is disabled for %s %s. Skipping export.",
                content_info["content_type"],
                context_key_string,
            )
            outcome = ExportStatus.SKIPPED_DISABLED
    except GitExportError as exc:
        LOGGER.exception(
            "Failed async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_id,
        )
        record_export_result(
            context_key,
            ExportStatus.FAILED,
            user=user,
            git_url=git_url,
            error_message=str(exc),
            git_output=_git_output(exc),
            exc=exc,
        )
        # Re-raised, not retried, so Celery records the failure; most push
        # and commit errors recur until someone fixes their cause.
        raise
    except Exception as exc:
        LOGGER.exception(
            "Unknown error occurred during async %s content export to git (%s id: %s)",
            content_info["content_type"],
            content_info["content_type"],
            content_id,
        )
        record_export_result(
            context_key,
            ExportStatus.FAILED,
            user=user,
            git_url=git_url,
            exc=exc,
        )
        raise
    else:
        record_export_result(context_key, outcome, user=user, git_url=git_url)


@shared_task(
    bind=True,
    autoretry_for=(requests.exceptions.RequestException,),
    retry_kwargs={"max_retries": 3, "countdown": 10},
)
def async_create_github_repo(  # noqa: C901, PLR0912, PLR0915
    self,
    context_key_str,
    export_content=False,  # noqa: FBT002
):
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
        record_export_result(
            context_key_str, ExportStatus.NOT_FOUND, error_message=response_msg
        )
        return False, response_msg
    except Exception as exc:
        LOGGER.exception("Failed to parse context key: %s", context_key_str)
        if not isinstance(exc, InvalidKeyError):  # unstorable key: log only
            record_export_result(
                context_key_str,
                ExportStatus.REPO_CREATION_FAILED,
                exc=exc,
            )
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
    max_retries = self.retry_kwargs.get("max_retries", 3)
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        # A malformed 201 body raises JSONDecodeError, also a RequestException.
        repo_data = (
            response.json() if response.status_code == status.HTTP_201_CREATED else None
        )
    except requests.exceptions.RequestException as exc:
        # autoretry_for retries these; record only the last attempt.
        if self.request.retries >= max_retries:
            record_export_result(
                context_key, ExportStatus.REPO_CREATION_FAILED, exc=exc
            )
        raise
    if response.status_code != status.HTTP_201_CREATED:
        try:
            error_body = response.json()
        except ValueError:  # e.g. a proxy's HTML error page
            error_body = response.text[:500]
        response_msg = f"Failed to create GitHub repository for {content_info['content_type']} {context_key} (HTTP {response.status_code}): {error_body}"  # noqa: E501
        LOGGER.error(response_msg)

        # Retry the task if we haven't exceeded max retries
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

        record_export_result(
            context_key, ExportStatus.REPO_CREATION_FAILED, error_message=response_msg
        )
        return False, response_msg

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
        record_export_result(
            context_key, ExportStatus.REPO_CREATION_FAILED, error_message=response_msg
        )

    if ssh_url and export_content:
        # Debounced like every other export, so it coalesces with an import
        # burst instead of racing it on the same clone directory. No author.
        schedule_export_with_debounce(context_key, lambda: None)

    return True, response_msg or ssh_url
