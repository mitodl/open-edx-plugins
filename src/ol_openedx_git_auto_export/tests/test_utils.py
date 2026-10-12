"""
Tests for the git export debounce logic in utils.py.
"""

from unittest import mock

import pytest
from django.core.cache import cache
from django.test import TestCase
from ol_openedx_git_auto_export.constants import (
    EXPORT_DEBOUNCE_DELAY,
    EXPORT_DEBOUNCE_PENDING_TTL,
    EXPORT_DEBOUNCE_TOKEN_TTL,
)
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError
from ol_openedx_git_auto_export.utils import (
    _get_library_publisher,
    claim_export_slot,
    current_export_token,
    debounce_cache_key,
    export_content_to_git,
    export_course_to_git,
    export_library_to_git,
    pending_cache_key,
    queue_export_task,
)
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2
from openedx.core.djangoapps.content_libraries.api import ContentLibraryNotFound

SIGNAL_COUNT = 3


def test_debounce_cache_key_is_versioned():
    """A rollback must not see this key as claimed by the new long-lived token."""
    assert debounce_cache_key("lib:org:slug") == "git_export_debounce_v2:lib:org:slug"


def test_claim_export_slot_uses_the_pending_ttl():
    with mock.patch("ol_openedx_git_auto_export.utils.cache.add") as mock_add:
        claim_export_slot("lib:org:slug")

    mock_add.assert_called_once_with(
        pending_cache_key("lib:org:slug"), "1", timeout=EXPORT_DEBOUNCE_PENDING_TTL
    )


def test_current_export_token_falls_back_to_the_callers_token():
    """on_error must be the caller's token; None would disable the debounce."""
    with mock.patch(
        "ol_openedx_git_auto_export.utils.cache.get",
        side_effect=RuntimeError("cache down"),
    ):
        assert current_export_token("lib:org:slug", "my-token") == "my-token"


def test_get_library_publisher_skips_v1_libraries():
    """V1 libraries have no published_by, and get_library() would raise."""
    with mock.patch("ol_openedx_git_auto_export.utils.get_library") as mock_get_library:
        assert _get_library_publisher(LibraryLocator("org", "lib")) is None

    mock_get_library.assert_not_called()


def test_get_library_publisher_normalises_a_blank_publisher():
    """An empty published_by must become None, not an empty commit author."""
    with mock.patch(
        "ol_openedx_git_auto_export.utils.get_library",
        return_value=mock.Mock(published_by=""),
    ):
        assert (
            _get_library_publisher(LibraryLocatorV2.from_string("lib:org:slug")) is None
        )


def test_queue_export_task_renews_the_slot():
    """The hand-off in _superseded keeps holding the slot instead of
    re-claiming it, so queueing must renew the TTL. Without this a burst that
    outlives EXPORT_DEBOUNCE_PENDING_TTL starts a second chain and two exports
    land on one clone directory."""
    with (
        mock.patch("ol_openedx_git_auto_export.utils.cache.set") as mock_set,
        mock.patch("ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"),
    ):
        queue_export_task("lib:org:slug", None, "a-token")

    mock_set.assert_called_once_with(
        pending_cache_key("lib:org:slug"), "1", timeout=EXPORT_DEBOUNCE_PENDING_TTL
    )


class TestExportDebounce(TestCase):
    """A burst queues one task; later signals only overwrite the token."""

    def setUp(self):
        cache.clear()

    def _assert_one_task_for_burst(self, content_key, mock_apply_async, mock_cache_set):
        # cache.set is also used to renew the pending marker, so select the
        # debounce-key writes only.
        token_writes = [
            call
            for call in mock_cache_set.call_args_list
            if call.args[0] == debounce_cache_key(content_key)
        ]
        tokens = [call.args[1] for call in token_writes]
        assert len(tokens) == SIGNAL_COUNT
        assert len(set(tokens)) == SIGNAL_COUNT, "each signal must get a fresh token"

        # The point of the fix: N signals, one Celery message.
        mock_apply_async.assert_called_once()
        queued_token = mock_apply_async.call_args.kwargs["kwargs"]["token"]
        assert queued_token == tokens[0]

        # The queued task will find this newer token and re-queue itself.
        assert cache.get(debounce_cache_key(content_key)) == tokens[-1]
        assert cache.get(pending_cache_key(content_key)) is not None

        # The token must outlive the whole burst.
        assert token_writes[-1].kwargs["timeout"] == EXPORT_DEBOUNCE_TOKEN_TTL
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
            # A burst, as a course import fires.
            with self.captureOnCommitCallbacks(execute=True):
                for _ in range(SIGNAL_COUNT):
                    export_library_to_git(library_key)

            tokens = self._assert_one_task_for_burst(
                library_key, mock_apply_async, mock_cache_set
            )

            # Once per burst, not per signal.
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
            # A burst, as one course save fires.
            with self.captureOnCommitCallbacks(execute=True):
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

    def test_schedules_via_a_robust_commit_hook(self):
        """Without robust=True, one failed hook cancels every later one."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.transaction.on_commit"
            ) as mock_on_commit,
        ):
            export_library_to_git(library_key)

        assert mock_on_commit.call_args.kwargs.get("robust") is True

    def test_failed_enqueue_releases_the_pending_marker(self):
        """A broker failure must not leave the marker behind, or the burst
        never exports."""
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
            self.captureOnCommitCallbacks(execute=True),
        ):
            export_library_to_git(library_key)

        assert cache.get(pending_cache_key(library_key)) is None

    def test_failed_publisher_lookup_still_queues_the_export(self):
        """Signals that lost the slot queued nothing, so this must still
        export -- unattributed."""
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
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            export_library_to_git(library_key)

        assert mock_apply_async.call_args.kwargs["args"] == [str(library_key), None]

    def test_failed_repo_dir_setup_does_not_export(self):
        """A failed export-dir setup must release the slot and skip the
        export, not queue one into a directory that was never created."""
        library_key = LibraryLocatorV2.from_string("lib:org:slug")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir",
                side_effect=RuntimeError("bad mount"),
            ),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
            self.captureOnCommitCallbacks(execute=True),
        ):
            export_library_to_git(library_key)

        mock_apply_async.assert_not_called()
        assert cache.get(pending_cache_key(library_key)) is None

    def test_export_is_queued_when_the_cache_backend_is_down(self):
        """A dead cache must fail open: export undebounced."""
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
            self.captureOnCommitCallbacks(execute=True),
        ):
            for _ in range(SIGNAL_COUNT):
                export_library_to_git(library_key)

        assert mock_apply_async.call_count == SIGNAL_COUNT

    def test_export_library_to_git_survives_missing_library(self):
        """A library not yet visible must still export, just without an author."""
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
            self.captureOnCommitCallbacks(execute=True),
        ):
            export_library_to_git(library_key)

        assert mock_apply_async.call_args.kwargs["args"] == [str(library_key), None]


@pytest.mark.parametrize(
    ("content_key", "is_library", "publisher_lookup"),
    [
        (
            CourseKey.from_string("course-v1:org+course+run"),
            False,
            "get_publisher_username",
        ),
        (LibraryLocator(org="org", library="lib"), True, "_get_library_publisher"),
        (LibraryLocatorV2(org="org", slug="lib"), True, "_get_library_publisher"),
    ],
)
@pytest.mark.parametrize("enabled", [True, False])
@pytest.mark.parametrize("dry_run", [True, False])
def test_export_content_to_git_queues_by_content_type(
    content_key, is_library, publisher_lookup, enabled, dry_run
):
    with (
        mock.patch(
            "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
            return_value=enabled,
        ) as mock_enabled,
        mock.patch(
            f"ol_openedx_git_auto_export.utils.{publisher_lookup}",
            return_value="publisher",
        ),
        mock.patch(
            "ol_openedx_git_auto_export.utils.get_content_info"
        ) as mock_content_info,
        mock.patch(
            "ol_openedx_git_auto_export.utils._queue_debounced_export"
        ) as mock_queue,
    ):
        assert export_content_to_git(content_key, dry_run=dry_run) is enabled

        mock_enabled.assert_called_once_with(is_library=is_library)
        assert mock_content_info.called is enabled
        if enabled and not dry_run:
            queued_key, resolve_user = mock_queue.call_args.args
            assert queued_key == content_key
            assert resolve_user() == "publisher"
        else:
            mock_queue.assert_not_called()


class TestExportContentToGitFailures(TestCase):
    """On-demand exports must surface queue failures, not swallow them."""

    def setUp(self):
        cache.clear()

    def test_failed_queue_raises_and_releases_the_slot(self):
        course_key = CourseKey.from_string("course-v1:org+course+run")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
            ),
            mock.patch("ol_openedx_git_auto_export.utils.get_content_info"),
            mock.patch("ol_openedx_git_auto_export.utils.get_publisher_username"),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                side_effect=RuntimeError("broker down"),
            ),
            pytest.raises(RuntimeError, match="broker down"),
        ):
            export_content_to_git(course_key)

        assert cache.get(pending_cache_key(course_key)) is None

    def test_failed_repo_dir_setup_raises(self):
        course_key = CourseKey.from_string("course-v1:org+course+run")

        with (
            mock.patch(
                "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
                return_value=True,
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir",
                side_effect=RuntimeError("bad mount"),
            ),
            mock.patch("ol_openedx_git_auto_export.utils.get_content_info"),
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
            ) as mock_apply_async,
            pytest.raises(RuntimeError, match="bad mount"),
        ):
            export_content_to_git(course_key)

        mock_apply_async.assert_not_called()


def test_export_content_to_git_raises_for_missing_content():
    with (
        mock.patch(
            "ol_openedx_git_auto_export.utils.is_auto_export_enabled",
            return_value=True,
        ),
        mock.patch(
            "ol_openedx_git_auto_export.utils.get_content_info",
            side_effect=ContentNotFoundError,
        ),
        mock.patch(
            "ol_openedx_git_auto_export.utils._queue_debounced_export"
        ) as mock_queue,
        pytest.raises(ContentNotFoundError),
    ):
        export_content_to_git(CourseKey.from_string("course-v1:org+course+run"))

    mock_queue.assert_not_called()
