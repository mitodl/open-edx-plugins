"""
Tests for the git export debounce logic in utils.py.
"""

from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import EXPORT_DEBOUNCE_CACHE_KEY
from ol_openedx_git_auto_export.utils import export_course_to_git, export_library_to_git
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocatorV2

EXPECTED_GENERATIONS = [1, 2]


class TestExportDebounce(TestCase):
    """Repeated publish signals for the same content must stamp each scheduled
    task with a strictly increasing generation, so only the task for the last
    signal matches the recorded generation when it runs."""

    def setUp(self):
        cache.clear()

    def test_export_library_to_git_stamps_increasing_generations(self):
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
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            # Simulate two LIBRARY_BLOCK_PUBLISHED/LIBRARY_CONTAINER_PUBLISHED
            # signals for the same library, as happens during a course import.
            export_library_to_git(library_key)
            export_library_to_git(library_key)

            generations = [
                call.kwargs["kwargs"]["generation"]
                for call in mock_apply_async.call_args_list
            ]
            assert generations == EXPECTED_GENERATIONS

            debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(
                content_key=str(library_key)
            )
            assert cache.get(debounce_key) == EXPECTED_GENERATIONS[-1]

    def test_export_course_to_git_stamps_increasing_generations(self):
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
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
        ):
            # Simulate two of the 10-30 COURSE_PUBLISHED signals a single
            # course save fires.
            export_course_to_git(course_key)
            export_course_to_git(course_key)

            generations = [
                call.kwargs["kwargs"]["generation"]
                for call in mock_apply_async.call_args_list
            ]
            assert generations == EXPECTED_GENERATIONS

            debounce_key = EXPORT_DEBOUNCE_CACHE_KEY.format(content_key=str(course_key))
            assert cache.get(debounce_key) == EXPECTED_GENERATIONS[-1]
