"""
Tests for the git export debounce logic in utils.py.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import (
    EXPORT_DEBOUNCE_CACHE_KEY,
    EXPORT_DEBOUNCE_DELAY,
)
from ol_openedx_git_auto_export.utils import export_course_to_git, export_library_to_git
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocatorV2

SIGNAL_COUNT = 3


class TestExportDebounce(TestCase):
    """Repeated publish signals for the same content must stamp each scheduled
    task with a fresh, distinct token, and the cache must end up holding only
    the last one -- so only the task for the last signal will match."""

    def setUp(self):
        cache.clear()

    def test_export_library_to_git_stamps_distinct_tokens(self):
        library_key = LibraryLocatorV2.from_string("lib:org:slug")
        user = mock.Mock(published_by="a-user")

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
                return_value=user,
            ),
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

            tokens = [
                call.kwargs["kwargs"]["token"]
                for call in mock_apply_async.call_args_list
            ]
            assert len(tokens) == SIGNAL_COUNT
            assert len(set(tokens)) == SIGNAL_COUNT, (
                "each signal must get a fresh token"
            )

            debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(
                content_key=str(library_key)
            )
            # Only the last signal's token is the one a woken task can match.
            assert cache.get(debounce_key) == tokens[-1]

            # Regression guard: the fix for a burst outliving a fixed window
            # depends on this key never expiring mid-burst.
            mock_cache_set.assert_called_with(debounce_key, tokens[-1], timeout=None)

            mock_apply_async.assert_called_with(
                args=[str(library_key), "a-user"],
                kwargs={"token": tokens[-1]},
                countdown=EXPORT_DEBOUNCE_DELAY,
            )

    def test_export_course_to_git_stamps_distinct_tokens(self):
        course_key = CourseKey.from_string("course-v1:org+course+run")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
            ),
            mock.patch("ol_openedx_git_auto_export.utils.modulestore"),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_publisher_username",
                return_value=None,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            # Simulate a few of the 10-30 COURSE_PUBLISHED signals a single
            # course save fires.
            for _ in range(SIGNAL_COUNT):
                export_course_to_git(course_key)

            tokens = [
                call.kwargs["kwargs"]["token"]
                for call in mock_apply_async.call_args_list
            ]
            assert len(tokens) == SIGNAL_COUNT
            assert len(set(tokens)) == SIGNAL_COUNT, (
                "each signal must get a fresh token"
            )

            debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=str(course_key))
            assert cache.get(debounce_key) == tokens[-1]

            mock_apply_async.assert_called_with(
                args=[str(course_key), None],
                kwargs={"token": tokens[-1]},
                countdown=EXPORT_DEBOUNCE_DELAY,
            )
