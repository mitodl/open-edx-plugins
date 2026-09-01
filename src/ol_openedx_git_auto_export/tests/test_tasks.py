"""
Tests for async_export_to_git's token-based staleness check.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import EXPORT_DEBOUNCE_CACHE_KEY
from ol_openedx_git_auto_export.tasks import async_export_to_git

CONTENT_KEY = "lib:org:slug"

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
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=CONTENT_KEY)

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
