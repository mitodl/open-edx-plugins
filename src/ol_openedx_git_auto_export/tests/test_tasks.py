"""
Tests for async_export_to_git's generation-based staleness check.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import EXPORT_DEBOUNCE_CACHE_KEY
from ol_openedx_git_auto_export.tasks import async_export_to_git


class TestAsyncExportToGitGenerationCheck(TestCase):
    """A task scheduled by the debounce logic must skip the export if a later
    signal has already superseded its generation."""

    def setUp(self):
        cache.clear()

    def test_skips_export_for_a_superseded_generation(self):
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key="lib:org:slug")
        cache.set(debounce_key, 2, timeout=None)

        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git("lib:org:slug", generation=1)

            # Superseded generation: bails out before even parsing the key.
            mock_key_cls.from_string.assert_not_called()

    def test_proceeds_when_generation_is_current(self):
        debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key="lib:org:slug")
        cache.set(debounce_key, 1, timeout=None)

        with mock.patch(
            "ol_openedx_git_auto_export.tasks.LearningContextKey"
        ) as mock_key_cls:
            async_export_to_git("lib:org:slug", generation=1)

            mock_key_cls.from_string.assert_called_once_with("lib:org:slug")
