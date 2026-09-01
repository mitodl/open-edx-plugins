"""
Tests for async_export_to_git's token-based staleness check.
"""

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
BURST_SIZE = 3
EXPECTED_TASK_RUNS = 2  # the burst's task, plus the one it re-queues

CASES = [
    # cached_token, call_token, should_proceed, should_requeue, case
    ("token-2", "token-1", False, True, "a newer signal recorded a different token"),
    ("token-1", "token-1", True, False, "its token is still current"),
    (None, "token-1", True, False, "the cache entry is missing (fail open)"),
    ("other-token", None, True, False, "called without a token (legacy path)"),
]


class TestAsyncExportToGitTokenCheck(TestCase):
    """A task queued by the debounce logic must export only when its token is
    still current, re-queue itself when a later signal superseded it, and never
    drop an export just because the cache entry is gone."""

    def setUp(self):
        cache.clear()

    def test_token_staleness_check(self):
        debounce_key = debounce_cache_key(CONTENT_KEY)
        pending_key = pending_cache_key(CONTENT_KEY)

        for cached_token, call_token, should_proceed, should_requeue, case in CASES:
            with self.subTest(case=case):
                cache.clear()
                cache.set(pending_key, "1", timeout=None)
                if cached_token is not None:
                    cache.set(debounce_key, cached_token, timeout=None)

                with (
                    mock.patch(
                        "ol_openedx_git_auto_export.tasks.LearningContextKey"
                    ) as mock_key_cls,
                    mock.patch(
                        "ol_openedx_git_auto_export.tasks.queue_export_task"
                    ) as mock_queue,
                ):
                    async_export_to_git(CONTENT_KEY, token=call_token)

                if should_proceed:
                    mock_key_cls.from_string.assert_called_once_with(CONTENT_KEY)
                else:
                    mock_key_cls.from_string.assert_not_called()

                if should_requeue:
                    mock_queue.assert_called_once_with(CONTENT_KEY, None, cached_token)
                else:
                    mock_queue.assert_not_called()

                # A token-carrying task is no longer queued once it wakes, so a
                # later signal must be free to queue a new one.
                if call_token:
                    assert cache.get(pending_key) is None
                else:
                    assert cache.get(pending_key) == "1"


class TestDebounceEndToEnd(TestCase):
    """A burst of signals, queued and then run exactly as Celery would, must
    cost far fewer tasks than signals and produce exactly one git export."""

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
                return_value=mock.Mock(published_by=None),
            ),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            for _ in range(BURST_SIZE):
                export_library_to_git(library_key)

            assert mock_apply_async.call_count == 1

            with (
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.get_content_info",
                    return_value={
                        "content_type": "library",
                        "content_module": mock.Mock(id=CONTENT_KEY),
                        "is_library": True,
                    },
                ),
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.ContentGitRepository"
                ) as mock_repo_cls,
                mock.patch("ol_openedx_git_auto_export.tasks.clear_stale_git_lock"),
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.export_to_git"
                ) as mock_export_to_git,
            ):
                mock_repo_cls.objects.get.return_value = mock.Mock(
                    is_export_enabled=True, git_url="git@example.com:repo.git"
                )

                # Run each queued task in turn, picking up any task a stale one
                # re-queues, exactly as Celery would.
                run = 0
                while run < mock_apply_async.call_count:
                    call = mock_apply_async.call_args_list[run]
                    async_export_to_git(*call.kwargs["args"], **call.kwargs["kwargs"])
                    run += 1

                assert run == EXPECTED_TASK_RUNS
                mock_export_to_git.assert_called_once()
