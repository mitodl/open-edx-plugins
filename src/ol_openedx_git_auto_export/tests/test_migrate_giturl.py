"""
Tests for the migrate_giturl management command.
"""

import inspect
from typing import TYPE_CHECKING, cast
from unittest import mock

from django.test import TestCase
from ol_openedx_git_auto_export.management.commands.migrate_giturl import Command
from ol_openedx_git_auto_export.models import ContentGitRepository
from ol_openedx_git_auto_export.tasks import async_create_github_repo
from opaque_keys.edx.keys import CourseKey

if TYPE_CHECKING:
    from collections.abc import Callable

COMMAND_MODULE = "ol_openedx_git_auto_export.management.commands.migrate_giturl"


def make_course(course_id_str, giturl):
    """Build a fake CourseOverview/course module pair for a given giturl."""
    course = mock.Mock()
    course.id = CourseKey.from_string(course_id_str)
    course_module = mock.Mock()
    course_module.giturl = giturl
    return course, course_module


class TestProcessRepositoriesInParallel(TestCase):
    """Tests for the parallel repository-creation dispatch path."""

    def _capture_dispatched_signatures(self, repos_to_create):
        """
        Run _process_repositories_in_parallel and return the Celery signatures
        the command handed to ``group``.
        """
        captured = []

        def fake_group(signatures):
            captured.extend(signatures)
            job = mock.Mock()
            job.apply_async.return_value = mock.Mock()
            return job

        command = Command()
        with (
            mock.patch.object(command, "_monitor_group_progress"),
            mock.patch.object(command, "_process_batch_results"),
            mock.patch(f"{COMMAND_MODULE}.group", side_effect=fake_group),
        ):
            command._process_repositories_in_parallel(repos_to_create, {})  # noqa: SLF001

        return captured

    def test_dispatched_kwargs_accepted_by_task(self):
        """
        Regression: the command must invoke async_create_github_repo with the
        ``export_content`` keyword. A stale ``export_course`` kwarg builds a
        valid signature but blows up inside Celery's argument check at
        apply_async time, so assert the dispatched kwargs bind against the
        real task signature.
        """
        captured = self._capture_dispatched_signatures(["course-v1:Org+A+R"])

        assert len(captured) == 1
        task_callable = cast("Callable[..., object]", async_create_github_repo.run)
        task_signature = inspect.signature(task_callable)
        for signature in captured:
            # ``self`` is bound by Celery, so stand it in here. Raises TypeError
            # if the command passes a keyword the task does not accept.
            task_signature.bind(None, *signature.args, **signature.kwargs)
            assert signature.kwargs == {"export_content": True}

    def test_dispatches_one_signature_per_repo(self):
        """A signature is dispatched for every course needing a repository."""
        repos = ["course-v1:Org+A+R", "course-v1:Org+B+R", "course-v1:Org+C+R"]
        captured = self._capture_dispatched_signatures(repos)

        assert len(captured) == len(repos)
        assert [signature.args[0] for signature in captured] == repos


class TestMigrateGiturlHandle(TestCase):
    """Tests for the command's top-level handle() flow and guard clauses."""

    def test_noop_when_auto_repo_creation_disabled(self):
        command = Command()
        with (
            mock.patch(
                f"{COMMAND_MODULE}.is_auto_repo_creation_enabled", return_value=False
            ),
            mock.patch(f"{COMMAND_MODULE}.CourseOverview") as mock_course_overview,
        ):
            command.handle(course_keys=[], all=False)

        mock_course_overview.objects.all.assert_not_called()

    def test_errors_without_course_keys_or_all(self):
        command = Command()
        command.stderr = mock.Mock()
        with mock.patch(
            f"{COMMAND_MODULE}.is_auto_repo_creation_enabled", return_value=True
        ):
            command.handle(course_keys=[], all=False)

        command.stderr.write.assert_called_once()

    def test_errors_with_both_course_keys_and_all(self):
        command = Command()
        command.stderr = mock.Mock()
        with mock.patch(
            f"{COMMAND_MODULE}.is_auto_repo_creation_enabled", return_value=True
        ):
            command.handle(course_keys=["course-v1:Org+A+R"], all=True)

        command.stderr.write.assert_called_once()

    def test_handle_categorizes_courses_and_dispatches_missing_repos(self):
        """
        A course with a giturl is recorded as an existing repo, while a
        duplicate giturl and a course without a giturl are queued for repo
        creation.
        """
        giturl = "git@github.com:org/a.git"
        course_a, module_a = make_course("course-v1:Org+A+R", giturl)
        course_b, module_b = make_course("course-v1:Org+B+R", giturl)
        course_c, module_c = make_course("course-v1:Org+C+R", None)

        modules = {
            course_a.id: module_a,
            course_b.id: module_b,
            course_c.id: module_c,
        }

        queryset = mock.MagicMock()
        queryset.__iter__.return_value = iter([course_a, course_b, course_c])
        queryset.count.return_value = 3

        command = Command()
        with (
            mock.patch(
                f"{COMMAND_MODULE}.is_auto_repo_creation_enabled", return_value=True
            ),
            mock.patch(f"{COMMAND_MODULE}.CourseOverview") as mock_course_overview,
            mock.patch(f"{COMMAND_MODULE}.modulestore") as mock_modulestore,
            mock.patch.object(
                command, "_process_repositories_in_parallel"
            ) as mock_process,
        ):
            mock_course_overview.objects.all.return_value.order_by.return_value = (
                queryset
            )
            mock_modulestore.return_value.get_course.side_effect = (
                lambda course_id, depth=1: modules[course_id]  # noqa: ARG005
            )

            command.handle(course_keys=[], all=True)

        assert ContentGitRepository.objects.filter(content_key=course_a.id).exists()

        mock_process.assert_called_once()
        queued_repos = mock_process.call_args.args[0]
        assert queued_repos == [course_b.id, course_c.id]
