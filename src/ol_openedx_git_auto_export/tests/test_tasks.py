"""
Tests for async_export_to_git's token-based staleness check.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.tasks import async_export_to_git
from ol_openedx_git_auto_export.utils import debounce_cache_key, export_library_to_git
from opaque_keys.edx.locator import LibraryLocatorV2

CONTENT_KEY = "lib:org:slug"
BURST_SIZE = 3

CASES = [
    # cached_token, call_token, should_proceed, case
    ("token-2", "token-1", False, "a newer signal recorded a different token"),
    ("token-1", "token-1", True, "its token is still current"),
    (None, "token-1", True, "the cache entry is missing (fail open, not dropped)"),
    ("some-other-tasks-token", None, True, "called without a token (legacy path)"),
]


class TestAsyncExportToGitTokenCheck(TestCase):
    """A task scheduled by the debounce logic must skip the export only when a
    later signal has genuinely superseded it, and must never drop an export
    just because the cache entry is gone."""

    def setUp(self):
        cache.clear()

    def test_token_staleness_check(self):
        debounce_key = debounce_cache_key(CONTENT_KEY)

        for cached_token, call_token, should_proceed, case in CASES:
            with self.subTest(case=case):
                cache.clear()
                if cached_token is not None:
                    cache.set(debounce_key, cached_token, timeout=None)

                with mock.patch(
                    "ol_openedx_git_auto_export.tasks.LearningContextKey"
                ) as mock_key_cls:
                    async_export_to_git(CONTENT_KEY, token=call_token)

                    if should_proceed:
                        mock_key_cls.from_string.assert_called_once_with(CONTENT_KEY)
                    else:
                        mock_key_cls.from_string.assert_not_called()


class TestDebounceEndToEnd(TestCase):
    """A full burst of signals, scheduled and then run in order exactly as
    Celery would, must result in exactly one real git export."""

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

            scheduled_calls = list(mock_apply_async.call_args_list)

        assert len(scheduled_calls) == BURST_SIZE

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

            # Run every scheduled task, in the order Celery would have.
            for call in scheduled_calls:
                async_export_to_git(*call.kwargs["args"], **call.kwargs["kwargs"])

            mock_export_to_git.assert_called_once()
