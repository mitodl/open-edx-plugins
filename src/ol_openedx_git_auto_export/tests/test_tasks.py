"""
Tests for async_export_to_git's token-based staleness check.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import EXPORT_DEBOUNCE_CACHE_KEY
from ol_openedx_git_auto_export.tasks import async_export_to_git

CONTENT_KEY = "lib:org:slug"


class TestAsyncExportToGitTokenCheck(TestCase):
    """A task scheduled by the debounce logic must skip the export only when a
    later signal has genuinely superseded it, and must never drop an export
    just because the cache entry is gone."""

    def setUp(self):
        cache.clear()

    def test_skips_export_when_a_newer_signal_recorded_a_different_token(self):
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=CONTENT_KEY)
        cache.set(debounce_key, "token-2", timeout=None)

        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git(CONTENT_KEY, token="token-1")  # noqa: S106

            # Superseded token: bails out before even parsing the key.
            mock_key_cls.from_string.assert_not_called()

    def test_proceeds_when_its_token_is_still_current(self):
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=CONTENT_KEY)
        cache.set(debounce_key, "token-1", timeout=None)

        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git(CONTENT_KEY, token="token-1")  # noqa: S106

            mock_key_cls.from_string.assert_called_once_with(CONTENT_KEY)

    def test_proceeds_when_the_cache_entry_is_missing(self):
        # No debounce_key ever set: e.g. evicted, or a cache flush/restart.
        # Must fail OPEN (export anyway), never silently drop the export.
        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git(CONTENT_KEY, token="token-1")  # noqa: S106

            mock_key_cls.from_string.assert_called_once_with(CONTENT_KEY)

    def test_legacy_call_without_a_token_always_proceeds(self):
        # async_create_github_repo calls async_export_to_git directly with no
        # token; this path must be unaffected by whatever is in the cache.
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=CONTENT_KEY)
        cache.set(debounce_key, "some-other-tasks-token", timeout=None)

        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git(CONTENT_KEY)

            mock_key_cls.from_string.assert_called_once_with(CONTENT_KEY)
