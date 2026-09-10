"""
Tests for async_export_to_git's token-based staleness check.
"""

from contextlib import ExitStack
from unittest import mock

from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.tasks import (
    async_create_github_repo,
    async_export_to_git,
)
from ol_openedx_git_auto_export.utils import (
    debounce_cache_key,
    export_library_to_git,
    pending_cache_key,
)
from opaque_keys.edx.locator import LibraryLocatorV2

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


def mock_export_collaborators(stack):
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
        mock.patch("ol_openedx_git_auto_export.tasks.clear_stale_git_lock")
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
