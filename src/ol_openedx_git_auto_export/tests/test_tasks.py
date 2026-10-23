"""
Tests for async_export_to_git: debounce, export lock, max wait and failures.
"""

import subprocess
import tempfile
import time
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

import pytest
from cms.djangoapps.contentstore.git_export_utils import GitExportError
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from ol_openedx_git_auto_export.constants import EXPORT_MAX_WAIT
from ol_openedx_git_auto_export.exceptions import ContentNotFoundError
from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.tasks import (
    async_create_github_repo,
    async_export_to_git,
)
from ol_openedx_git_auto_export.utils import (
    burst_start_cache_key,
    debounce_cache_key,
    export_library_to_git,
    export_lock_cache_key,
    pending_cache_key,
    queue_debounced_export,
)
from opaque_keys.edx.locator import LibraryLocatorV2

from ol_openedx_git_auto_export import utils

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
    (
        "other-token",
        None,
        True,
        "called without a token (a message from before the token existed)",
    ),
]


def mock_export_collaborators(stack, *, index_unlocked=True):
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
    # Patch only .objects: leaving ContentGitRepository itself real keeps
    # DoesNotExist an exception class, so the except clauses stay reachable.
    objects = stack.enter_context(mock.patch.object(ContentGitRepository, "objects"))
    objects.get.return_value = mock.Mock(
        is_export_enabled=True, git_url="git@example.com:repo.git"
    )
    stack.enter_context(
        mock.patch(
            "ol_openedx_git_auto_export.tasks.clear_stale_git_lock",
            return_value=index_unlocked,
        )
    )
    return stack.enter_context(
        mock.patch("ol_openedx_git_auto_export.tasks.export_to_git")
    )


class TestAsyncExportToGitTokenCheck(TestCase):
    """A task exports only while its token is current, and never drops an
    export because the cache entry is gone."""

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

                # Assert the export ran, not just that the check passed.
                assert mock_export_to_git.called is should_export

                if should_export:
                    mock_queue.assert_not_called()
                else:
                    # The user must be carried forward, not dropped.
                    mock_queue.assert_called_once_with(CONTENT_KEY, USER, cached_token)

                # Exporting frees the slot; handing off keeps holding it;
                # the no-token path never touches it.
                if should_export and call_token:
                    assert cache.get(pending_key) is None
                else:
                    assert cache.get(pending_key) == "1"

    def test_exports_current_state_when_the_requeue_fails_to_enqueue(self):
        """If queuing the replacement fails, export current state instead of
        leaving the newer signal with nothing, and don't strand the slot."""
        debounce_key = debounce_cache_key(CONTENT_KEY)
        pending_key = pending_cache_key(CONTENT_KEY)
        cache.set(pending_key, "1", timeout=None)
        cache.set(debounce_key, "newer-token", timeout=None)

        with (
            ExitStack() as stack,
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                side_effect=RuntimeError("broker down"),
            ),
        ):
            mock_export_to_git = mock_export_collaborators(stack)
            async_export_to_git(CONTENT_KEY, user=USER, token="original-token")  # noqa: S106

        mock_export_to_git.assert_called_once()
        assert cache.get(pending_key) is None

    def test_failed_requeue_then_a_wait_keeps_a_burst_start(self):
        """The failed re-queue released the slot and burst start; carrying on
        as their owner without re-claiming them would leave a later wait with
        no max wait."""
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        cache.set(debounce_cache_key(CONTENT_KEY), "newer-token", timeout=None)
        cache.set(export_lock_cache_key(CONTENT_KEY), "1", timeout=None)

        with (
            ExitStack() as stack,
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                side_effect=[RuntimeError("broker blip"), None],
            ) as mock_apply_async,
        ):
            mock_export_to_git = mock_export_collaborators(stack)
            async_export_to_git(CONTENT_KEY, user=USER, token="original-token")  # noqa: S106

        mock_export_to_git.assert_not_called()
        assert mock_apply_async.call_count == 2  # noqa: PLR2004
        assert cache.get(pending_cache_key(CONTENT_KEY)) == "1"
        assert cache.get(burst_start_cache_key(CONTENT_KEY)) is not None

    def test_failed_requeue_leaves_a_newer_burst_alone(self):
        """A publish that claims the slot the failed re-queue freed owns it;
        the old task must neither export over it nor release its state."""
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        cache.set(debounce_cache_key(CONTENT_KEY), "newer-token", timeout=None)
        real_release = utils.release_export_slot

        def release_then_newer_publish(content_key):
            real_release(content_key)
            cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
            cache.set(burst_start_cache_key(CONTENT_KEY), 1000.0, timeout=None)

        with (
            ExitStack() as stack,
            mock.patch(
                "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                side_effect=RuntimeError("broker blip"),
            ),
            mock.patch(
                "ol_openedx_git_auto_export.utils.release_export_slot",
                side_effect=release_then_newer_publish,
            ),
        ):
            mock_export_to_git = mock_export_collaborators(stack)
            async_export_to_git(CONTENT_KEY, user=USER, token="original-token")  # noqa: S106

        mock_export_to_git.assert_not_called()
        assert cache.get(pending_cache_key(CONTENT_KEY)) == "1"
        assert cache.get(burst_start_cache_key(CONTENT_KEY)) == 1000.0  # noqa: PLR2004


class TestExportFailuresAreReported(TestCase):
    """A failed export must fail the Celery task, not log and succeed."""

    def setUp(self):
        cache.clear()

    def test_failures_propagate(self):
        for error in (GitExportError("Unable to commit changes"), RuntimeError("boom")):
            with self.subTest(error=type(error).__name__), ExitStack() as stack:
                mock_export_collaborators(stack).side_effect = error
                with pytest.raises(type(error)):
                    async_export_to_git(CONTENT_KEY, user=USER)

    def test_only_an_unchanged_export_is_not_a_failure(self):
        """export_to_git raises CANNOT_COMMIT for both cases; git's output
        is the only difference."""
        cases = [
            (b"On branch main\nnothing to commit, working tree clean\n", False),
            (b"fatal: Unable to create '.git/index.lock': File exists.\n", True),
            ("On branch main\nnothing to commit, working tree clean\n", False),
            (None, True),
        ]
        for output, should_raise in cases:
            with self.subTest(output=output), ExitStack() as stack:
                error = GitExportError(GitExportError.CANNOT_COMMIT)
                error.__cause__ = subprocess.CalledProcessError(1, "git", output)
                mock_export_collaborators(stack).side_effect = error
                if should_raise:
                    with pytest.raises(GitExportError):
                        async_export_to_git(CONTENT_KEY, user=USER)
                else:
                    async_export_to_git(CONTENT_KEY, user=USER)

    def test_content_resolution_failure_propagates(self):
        with (
            mock.patch(
                "ol_openedx_git_auto_export.tasks.get_content_info",
                side_effect=RuntimeError("modulestore down"),
            ),
            pytest.raises(RuntimeError, match="modulestore down"),
        ):
            async_export_to_git(CONTENT_KEY, user=USER)

    def test_missing_content_is_not_a_failure(self):
        with mock.patch(
            "ol_openedx_git_auto_export.tasks.get_content_info",
            side_effect=ContentNotFoundError("gone"),
        ):
            async_export_to_git(CONTENT_KEY, user=USER)


class TestMaxWait(TestCase):
    """A burst that keeps postponing its export is exported anyway."""

    def setUp(self):
        cache.clear()

    def test_stale_task_exports_once_the_burst_waited_too_long(self):
        cases = [
            # burst age, should_export
            (EXPORT_MAX_WAIT + 1, True),
            (EXPORT_MAX_WAIT - 60, False),
        ]
        for age, should_export in cases:
            with self.subTest(age=age), ExitStack() as stack:
                cache.clear()
                cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
                cache.set(debounce_cache_key(CONTENT_KEY), "newer", timeout=None)
                cache.set(
                    burst_start_cache_key(CONTENT_KEY), time.time() - age, timeout=None
                )
                mock_export_to_git = mock_export_collaborators(stack)
                mock_queue = stack.enter_context(
                    mock.patch("ol_openedx_git_auto_export.tasks.queue_export_task")
                )
                async_export_to_git(CONTENT_KEY, user=USER, token="older")  # noqa: S106

                assert mock_export_to_git.called is should_export
                assert mock_queue.called is not should_export
                if should_export:
                    # The burst is over: the next signal starts a new one.
                    assert cache.get(pending_cache_key(CONTENT_KEY)) is None
                    assert cache.get(burst_start_cache_key(CONTENT_KEY)) is None


class TestExportLock(TestCase):
    """Two exports of one content item must not share its clone directory."""

    def setUp(self):
        cache.clear()

    def test_export_holds_the_lock_and_releases_it(self):
        lock_key = export_lock_cache_key(CONTENT_KEY)
        for error in (None, GitExportError("Unable to push changes")):
            with self.subTest(error=error), ExitStack() as stack:
                held = []
                mock_export = mock_export_collaborators(stack)

                def export(*_args, error=error, held=held, **_kwargs):
                    held.append(cache.get(lock_key))
                    if error:
                        raise error

                mock_export.side_effect = export
                if error:
                    with pytest.raises(GitExportError):
                        async_export_to_git(CONTENT_KEY, user=USER)
                else:
                    async_export_to_git(CONTENT_KEY, user=USER)

                assert held == ["1"]
                assert cache.get(lock_key) is None

    def test_held_lock_waits_keeping_the_slot_and_the_burst_start(self):
        """Waiting must neither free the slot nor end the burst: a wait that
        restarted the burst would also restart its max wait."""
        lock_key = export_lock_cache_key(CONTENT_KEY)
        cache.set(lock_key, "1", timeout=None)
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        cache.set(debounce_cache_key(CONTENT_KEY), "current", timeout=None)
        cache.set(burst_start_cache_key(CONTENT_KEY), 1000.0, timeout=None)

        with ExitStack() as stack:
            mock_export_to_git = mock_export_collaborators(stack)
            mock_queue = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.queue_export_task")
            )
            async_export_to_git(CONTENT_KEY, user=USER, token="current")  # noqa: S106

        mock_export_to_git.assert_not_called()
        mock_queue.assert_called_once_with(CONTENT_KEY, USER, "current")
        assert cache.get(lock_key) == "1"
        assert cache.get(pending_cache_key(CONTENT_KEY)) == "1"
        assert cache.get(burst_start_cache_key(CONTENT_KEY)) == 1000.0  # noqa: PLR2004

    def test_without_a_token_a_wait_queues_a_debounced_follow_up(self):
        for trigger in ("held export lock", "young index.lock"):
            with self.subTest(trigger=trigger), ExitStack() as stack:
                cache.clear()
                if trigger == "held export lock":
                    cache.set(export_lock_cache_key(CONTENT_KEY), "1", timeout=None)
                mock_export_to_git = mock_export_collaborators(
                    stack, index_unlocked=trigger != "young index.lock"
                )
                mock_follow_up = stack.enter_context(
                    mock.patch(
                        "ol_openedx_git_auto_export.tasks.queue_debounced_export"
                    )
                )
                async_export_to_git(CONTENT_KEY, user=USER)

                mock_export_to_git.assert_not_called()
                key, resolve_user = mock_follow_up.call_args.args
                assert key == CONTENT_KEY
                assert resolve_user() == USER

    def test_publish_during_the_export_keeps_its_burst_start(self):
        """A burst that begins while this export runs must keep its start,
        or nothing bounds how long it can postpone its own export."""
        with ExitStack() as stack:
            mock_export = mock_export_collaborators(stack)
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
                )
            )
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
                )
            )
            mock_export.side_effect = lambda *_a, **_k: queue_debounced_export(
                CONTENT_KEY, lambda: None
            )
            async_export_to_git(CONTENT_KEY, user=USER, token="current")  # noqa: S106

        started = cache.get(burst_start_cache_key(CONTENT_KEY))
        assert started is not None
        assert time.time() - started < 5  # noqa: PLR2004

    def test_young_index_lock_waits_keeping_an_overdue_burst(self):
        """A killed export can leave an index.lock too young to remove. The
        task must wait for it without ending the burst: a forced, overdue
        export that restarted its burst could be postponed another max wait."""
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        cache.set(debounce_cache_key(CONTENT_KEY), "newer", timeout=None)
        overdue = time.time() - EXPORT_MAX_WAIT - 1
        cache.set(burst_start_cache_key(CONTENT_KEY), overdue, timeout=None)

        with ExitStack() as stack:
            mock_export = mock_export_collaborators(stack, index_unlocked=False)
            mock_queue = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.queue_export_task")
            )
            async_export_to_git(CONTENT_KEY, user=USER, token="older")  # noqa: S106

        mock_export.assert_not_called()
        mock_queue.assert_called_once_with(CONTENT_KEY, USER, "newer")
        assert cache.get(pending_cache_key(CONTENT_KEY)) == "1"
        assert cache.get(burst_start_cache_key(CONTENT_KEY)) == overdue
        assert cache.get(export_lock_cache_key(CONTENT_KEY)) is None

    def test_failed_wait_frees_the_slot_and_the_lock(self):
        """With the broker down the wait can't be queued: the task must fail,
        and leave nothing behind that would swallow the next publish."""
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        cache.set(burst_start_cache_key(CONTENT_KEY), 1000.0, timeout=None)
        with ExitStack() as stack:
            mock_export = mock_export_collaborators(stack, index_unlocked=False)
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async",
                    side_effect=RuntimeError("broker down"),
                )
            )
            with pytest.raises(RuntimeError, match="broker down"):
                async_export_to_git(CONTENT_KEY, user=USER, token="current")  # noqa: S106

        mock_export.assert_not_called()
        assert cache.get(pending_cache_key(CONTENT_KEY)) is None
        assert cache.get(burst_start_cache_key(CONTENT_KEY)) is None
        assert cache.get(export_lock_cache_key(CONTENT_KEY)) is None

    def test_failed_index_check_frees_the_slot(self):
        """The index.lock check runs while the task still holds the slot; if
        it raised with the slot held, the next publishes would see an export
        queued that never runs."""
        cache.set(pending_cache_key(CONTENT_KEY), "1", timeout=None)
        with ExitStack() as stack:
            mock_export = mock_export_collaborators(stack)
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.clear_stale_git_lock",
                    side_effect=PermissionError("shared volume"),
                )
            )
            with pytest.raises(PermissionError):
                async_export_to_git(CONTENT_KEY, user=USER, token="current")  # noqa: S106

        mock_export.assert_not_called()
        assert cache.get(pending_cache_key(CONTENT_KEY)) is None
        assert cache.get(export_lock_cache_key(CONTENT_KEY)) is None

    def test_cache_outage_exports_without_releasing_anothers_lock(self):
        """With the cache down the export goes ahead unowned; if the cache
        recovers meanwhile, the lock it finds belongs to someone else."""
        lock_key = export_lock_cache_key(CONTENT_KEY)
        with ExitStack() as stack:
            mock_export = mock_export_collaborators(stack)
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.utils.cache.add",
                    side_effect=RuntimeError("cache down"),
                )
            )
            mock_export.side_effect = lambda *_a, **_k: cache.set(
                lock_key, "other-export", timeout=None
            )
            async_export_to_git(CONTENT_KEY, user=USER)

        mock_export.assert_called_once()
        assert cache.get(lock_key) == "other-export"


class TestIndexLockCheck(TestCase):
    """The index.lock check against a real repository row and clone dir."""

    def setUp(self):
        cache.clear()

    def test_young_index_lock_in_the_registered_clone_waits(self):
        ContentGitRepository.objects.create(
            content_key=LibraryLocatorV2.from_string(CONTENT_KEY),
            git_url="git@example.com:org/repo.git",
        )
        with tempfile.TemporaryDirectory() as export_dir, ExitStack() as stack:
            index_lock = Path(export_dir) / "repo" / ".git" / "index.lock"
            index_lock.parent.mkdir(parents=True)
            index_lock.touch()
            stack.enter_context(override_settings(GIT_REPO_EXPORT_DIR=export_dir))
            mock_export = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.export_to_git")
            )
            stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.get_content_info")
            )
            mock_queue = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.queue_export_task")
            )
            async_export_to_git(CONTENT_KEY, user=USER, token="current")  # noqa: S106

            assert index_lock.exists()
        mock_export.assert_not_called()
        mock_queue.assert_called_once()

    def test_unregistered_content_skips_the_check(self):
        with ExitStack() as stack:
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
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.is_auto_repo_creation_enabled",
                    return_value=False,
                )
            )
            mock_check = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.clear_stale_git_lock")
            )
            mock_export = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.export_to_git")
            )
            async_export_to_git(CONTENT_KEY, user=USER)

        mock_check.assert_not_called()
        mock_export.assert_not_called()


class TestMissingRepositoryHandling(TestCase):
    """A content key with no registered repository must not crash the task."""

    def setUp(self):
        cache.clear()

    def test_repo_creation_check_failure_does_not_crash_the_task(self):
        """ImproperlyConfigured from missing GitHub settings isn't caught by
        the sibling except clauses, so the inner guard has to."""
        with ExitStack() as stack:
            mock_export_to_git = mock_export_collaborators(stack)
            objects = stack.enter_context(
                mock.patch.object(ContentGitRepository, "objects")
            )
            objects.get.side_effect = ContentGitRepository.DoesNotExist
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.is_auto_repo_creation_enabled",
                    side_effect=ImproperlyConfigured("no GITHUB_ACCESS_TOKEN"),
                )
            )
            mock_create = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.async_create_github_repo")
            )

            async_export_to_git(CONTENT_KEY)

        mock_export_to_git.assert_not_called()
        mock_create.delay.assert_not_called()


@override_settings(
    GITHUB_ORG_API_URL="https://api.github.com/orgs/test-org",
    GITHUB_ACCESS_TOKEN="test-token",  # noqa: S106
    CMS_BASE="studio.example.com",
    GIT_AUTO_EXPORT_AUTHORING_URL_PREFIX="/authoring",
)
class TestRepoCreationExportIsDebounced(TestCase):
    """The post-creation export must go through the debounce. Inline, the
    plugin's only serialization point couldn't see it, so it could run
    concurrently with a burst's export on the same clone directory."""

    def setUp(self):
        cache.clear()

    def test_created_repo_queues_a_debounced_export(self):
        library_key = LibraryLocatorV2.from_string(CONTENT_KEY)

        with ExitStack() as stack:
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.get_content_info",
                    return_value={
                        "content_type": "library",
                        "content_module": mock.Mock(title="A Library"),
                        "is_v2_library": True,
                        "is_library": True,
                    },
                )
            )
            objects = stack.enter_context(
                mock.patch.object(ContentGitRepository, "objects")
            )
            objects.filter.return_value.exists.return_value = False
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.requests.post",
                    return_value=mock.Mock(
                        status_code=201,
                        json=lambda: {"ssh_url": "git@example.com:repo.git"},
                    ),
                )
            )
            stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.utils.get_or_create_git_export_repo_dir"
                )
            )
            mock_export_to_git = stack.enter_context(
                mock.patch("ol_openedx_git_auto_export.tasks.export_to_git")
            )
            mock_apply_async = stack.enter_context(
                mock.patch(
                    "ol_openedx_git_auto_export.tasks.async_export_to_git.apply_async"
                )
            )

            # on_commit hooks never fire inside TestCase's rolled-back
            # transaction without this.
            with self.captureOnCommitCallbacks(execute=True):
                async_create_github_repo(str(library_key), export_content=True)

        # A token is what lets this and the burst's task collapse into one.
        mock_export_to_git.assert_not_called()
        mock_apply_async.assert_called_once()
        assert mock_apply_async.call_args.kwargs["kwargs"]["token"]
        assert mock_apply_async.call_args.kwargs["args"] == [str(library_key), None]
        assert cache.get(pending_cache_key(library_key)) is not None


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
            with self.captureOnCommitCallbacks(execute=True):
                for _ in range(BURST_SIZE):
                    export_library_to_git(library_key)

            assert mock_apply_async.call_count == 1

            with ExitStack() as stack:
                mock_export_to_git = mock_export_collaborators(stack)

                # Iteration picks up whatever a stale task re-queues.
                for call in mock_apply_async.call_args_list:
                    async_export_to_git(*call.kwargs["args"], **call.kwargs["kwargs"])

                assert mock_apply_async.call_count == EXPECTED_TASK_RUNS
                mock_export_to_git.assert_called_once()
                assert mock_export_to_git.call_args.kwargs["user"] == USER
