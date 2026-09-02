"""
Tests for the git export debounce logic in utils.py.
"""

from unittest import mock

import pytest
from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import EXPORT_DEBOUNCE_DELAY
from ol_openedx_git_auto_export.utils import (
    debounce_cache_key,
    export_course_to_git,
    export_library_to_git,
    pending_cache_key,
)
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.api import ContentLibraryNotFound

SIGNAL_COUNT = 3


class TestExportDebounce(TestCase):
    """A burst of publish signals for the same content must queue exactly one
    task -- carrying the first signal's token -- while every later signal only
    overwrites the token, so the queued task can tell the burst moved on."""

    def setUp(self):
        cache.clear()

    def _assert_one_task_for_burst(self, content_key, mock_apply_async, mock_cache_set):
        tokens = [call.args[1] for call in mock_cache_set.call_args_list]
        assert len(tokens) == SIGNAL_COUNT
        assert len(set(tokens)) == SIGNAL_COUNT, "each signal must get a fresh token"

        # The point of the fix: N signals, one Celery message.
        mock_apply_async.assert_called_once()
        queued_token = mock_apply_async.call_args.kwargs["kwargs"]["token"]
        assert queued_token == tokens[0]

        # The queued task will find this newer token and re-queue itself.
        assert cache.get(debounce_cache_key(content_key)) == tokens[-1]
        assert cache.get(pending_cache_key(content_key)) is not None

        # Regression guard: the debounce token must outlive the whole burst.
        mock_cache_set.assert_called_with(
            debounce_cache_key(content_key), tokens[-1], timeout=None
        )
        return tokens

    def test_export_library_to_git_queues_one_task_per_burst(self):
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

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
                return_value=mock.Mock(published_by="a-user"),
            ) as mock_get_library,
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
            mock.patch(
                "ol_openedx_git_auto_export.utils.cache.set", wraps=cache.set
            ) as mock_cache_set,
        ):
            # Simulate a burst of LIBRARY_BLOCK_PUBLISHED/LIBRARY_CONTAINER_PUBLISHED
            # signals for the same library, as happens during a course import.
            for _ in range(SIGNAL_COUNT):
                export_library_to_git(library_key)

            tokens = self._assert_one_task_for_burst(
                library_key, mock_apply_async, mock_cache_set
            )

            # get_library() costs several queries, so it must run once per
            # burst, not once per signal.
            mock_get_library.assert_called_once_with(library_key)

            mock_apply_async.assert_called_once_with(
                args=[str(library_key), "a-user"],
                kwargs={"token": tokens[0]},
                countdown=EXPORT_DEBOUNCE_DELAY,
            )

    def test_export_course_to_git_queues_one_task_per_burst(self):
        course_key = CourseKey.from_string("course-v1:org+course+run")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
            ),
            mock.patch("ol_openedx_git_auto_export.utils.modulestore") as mock_store,
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_publisher_username",
                return_value=None,
            ) as mock_publisher,
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
            mock.patch(
                "ol_openedx_git_auto_export.utils.cache.set", wraps=cache.set
            ) as mock_cache_set,
        ):
            # Simulate a few of the 10-30 COURSE_PUBLISHED signals a single
            # course save fires.
            for _ in range(SIGNAL_COUNT):
                export_course_to_git(course_key)

            tokens = self._assert_one_task_for_burst(
                course_key, mock_apply_async, mock_cache_set
            )

            # The course fetch and publisher lookup must run once per burst.
            mock_store.assert_called_once()
            mock_publisher.assert_called_once()

            mock_apply_async.assert_called_once_with(
                args=[str(course_key), None],
                kwargs={"token": tokens[0]},
                countdown=EXPORT_DEBOUNCE_DELAY,
            )

    def test_failed_enqueue_releases_the_pending_marker(self):
        """A broker failure must not leave the marker behind: every signal for
        the next minute would then think a task is queued and the burst would
        never export."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

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
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                side_effect=RuntimeError("broker down"),
            ),
            pytest.raises(RuntimeError),
        ):
            export_library_to_git(library_key)

        assert cache.get(pending_cache_key(library_key)) is None

    def test_failed_publisher_lookup_releases_the_pending_marker(self):
        """The publisher lookup runs while holding the slot, so it must release
        it if it blows up -- otherwise the burst is stranded for the marker's
        whole lifetime."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

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
                side_effect=RuntimeError("database down"),
            ),
            pytest.raises(RuntimeError),
        ):
            export_library_to_git(library_key)

        assert cache.get(pending_cache_key(library_key)) is None

    def test_export_is_queued_when_the_cache_backend_is_down(self):
        """A dead cache must fail open -- export undebounced rather than raise
        out of the publish request or drop the export."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")
        cache_down = mock.Mock(side_effect=RuntimeError("cache down"))

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
            mock.patch("ol_openedx_git_auto_export.utils.cache.set", cache_down),
            mock.patch("ol_openedx_git_auto_export.utils.cache.add", cache_down),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            for _ in range(SIGNAL_COUNT):
                export_library_to_git(library_key)

            assert mock_apply_async.call_count == SIGNAL_COUNT

    def test_export_library_to_git_survives_missing_library(self):
        """A library not yet visible must still be exported, just without an
        author -- the task re-resolves it when it runs."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

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
                side_effect=ContentLibraryNotFound,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            export_library_to_git(library_key)

            assert mock_apply_async.call_args.kwargs["args"] == [str(library_key), None]
