"""
Tests for async_export_to_git's token-based staleness check.
"""

from contextlib import ExitStack
from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.tasks import async_export_to_git
from ol_openedx_git_auto_export.utils import (
    debounce_cache_key,
    export_library_to_git,
    pending_cache_key,
)
from opaque_keys.edx.locator import LibraryLocatorV2

CONTENT_KEY = "lib:org:slug"
USER = "a-user"
BURST_SIZE = 3
EXPECTED_TASK_RUNS = 2  # the burst's task, plus the one it re-queues

CASES = [
    # A task either exports or re-queues itself, never both.
    # cached_token, call_token, should_export, case
    ("token-2", "token-1", False, "a newer signal recorded a different token"),
    ("token-1", "token-1", True, "its token is still current"),
    (None, "token-1", True, "the cache entry is missing (fail open)"),
    ("other-token", None, True, "called without a token (legacy path)"),
]


def mock_export_collaborators(stack):
    """Patch everything async_export_to_git needs to reach export_to_git."""
    stack.enter_context(
        mock.patch(
            "ol_openedx_git_auto_export.tasks.get_content_info",
            return_value={
                "content_type": "library",
                "content_module": mock.Mock(id=CONTENT_KEY),
                "is_library": True,
            },
        )
    )
    repo_cls = stack.enter_context(
        mock.patch("ol_openedx_git_auto_export.tasks.ContentGitRepository")
    )
    repo_cls.objects.get.return_value = mock.Mock(
        is_export_enabled=True, git_url="git@example.com:repo.git"
    )
    stack.enter_context(
        mock.patch("ol_openedx_git_auto_export.tasks.clear_stale_git_lock")
    )
    return stack.enter_context(
        mock.patch("ol_openedx_git_auto_export.tasks.export_to_git")
    )


class TestAsyncExportToGitTokenCheck(TestCase):
    """A queued task must export only while its token is current, and must
    never drop an export just because the cache entry is gone."""

    def setUp(self):
        cache.clear()

    def test_token_staleness_check(self):
        debounce_key = debounce_cache_key(CONTENT_KEY)
        pending_key = pending_cache_key(CONTENT_KEY)

        for cached_token, call_token, should_export, case in CASES:
            with self.subTest(case=case):
                cache.clear()
                cache.set(pending_key, "1", timeout=None)
                if cached_token is not None:
                    cache.set(debounce_key, cached_token, timeout=None)

                with ExitStack() as stack:
                    mock_export_to_git = mock_export_collaborators(stack)
                    mock_queue = stack.enter_context(
                        mock.patch("ol_openedx_git_auto_export.tasks.queue_export_task")
                    )
                    async_export_to_git(CONTENT_KEY, user=USER, token=call_token)

                # Assert the export ran, not just that the token check passed:
                # a broad except would hide a broken export path.
                assert mock_export_to_git.called is should_export

                if should_export:
                    mock_queue.assert_not_called()
                else:
                    # The user must be carried forward, not dropped.
                    mock_queue.assert_called_once_with(CONTENT_KEY, USER, cached_token)

                # Once awake, a task must free the slot for the next signal.
                if call_token:
                    assert cache.get(pending_key) is None
                else:
                    assert cache.get(pending_key) == "1"


class TestDebounceEndToEnd(TestCase):
    """A burst must cost far fewer tasks than signals and produce one export."""

    def setUp(self):
        cache.clear()

    def test_burst_collapses_to_one_real_export(self):
        library_key = LibraryLocatorV2.from_string(CONTENT_KEY)

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_library",
                return_value=mock.Mock(published_by=USER),
            ),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            for _ in range(BURST_SIZE):
                export_library_to_git(library_key)

            assert mock_apply_async.call_count == 1

            with ExitStack() as stack:
                mock_export_to_git = mock_export_collaborators(stack)

                # Run each queued task as Celery would; the iteration picks up
                # whatever a stale task re-queues.
                for call in mock_apply_async.call_args_list:
                    async_export_to_git(*call.kwargs["args"], **call.kwargs["kwargs"])

                assert mock_apply_async.call_count == EXPECTED_TASK_RUNS
                mock_export_to_git.assert_called_once()
                assert mock_export_to_git.call_args.kwargs["user"] == USER
