"""
Tests for the sync_problem_actions management command.
"""

from io import StringIO
from unittest import mock

import pytest
from common.djangoapps.student.tests.factories import UserFactory
from ddt import ddt, named_data, unpack
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from ol_openedx_course_sync.constants import (
    ACTION_RESCORE,
    ACTION_RESET_ATTEMPTS,
    STATUS_ALREADY_RUNNING,
    STATUS_FAILED,
    STATUS_SUBMITTED,
)
from openedx.core.djangolib.testing.utils import skip_unless_lms

COURSE_KEY = "course-v1:org+course+run"
PROBLEM_KEY = "block-v1:org+course+run+type@problem+block@test_problem"
SUBMIT_PATH = (
    "ol_openedx_course_sync.management.commands.sync_problem_actions"
    ".submit_problem_action_for_synced_courses"
)


@ddt
@skip_unless_lms
class TestSyncProblemActionsCommand(TestCase):
    """
    Test the command's argument validation and its reporting of per-course results.

    The fan-out itself is covered in test_utils; what matters here is that the
    command surfaces every status the fan-out can return, since each status
    carries a different set of keys.
    """

    def setUp(self):
        super().setUp()
        self.user = UserFactory.create(username="courses_service_worker")

    def _run(self, results, action=ACTION_RESET_ATTEMPTS):
        """Run the command with the fan-out mocked out, returning its stdout."""
        out = StringIO()
        with mock.patch(SUBMIT_PATH, return_value=results) as mock_submit:
            call_command(
                "sync_problem_actions", action, COURSE_KEY, PROBLEM_KEY, stdout=out
            )
        return out.getvalue(), mock_submit

    @named_data(
        ["invalid_course_key", ("nope", PROBLEM_KEY), {}, "Invalid source course key"],
        ["invalid_problem_key", (COURSE_KEY, "nope"), {}, "Invalid problem usage key"],
        [
            "unknown_username",
            (COURSE_KEY, PROBLEM_KEY),
            {"username": "no_such_user"},
            "User not found",
        ],
    )
    @unpack
    def test_bad_input_fails_before_submitting(self, args, kwargs, expected_error):
        """Every argument is validated before a single task is submitted."""
        with (
            mock.patch(SUBMIT_PATH) as mock_submit,
            pytest.raises(CommandError, match=expected_error),
        ):
            call_command("sync_problem_actions", ACTION_RESET_ATTEMPTS, *args, **kwargs)

        mock_submit.assert_not_called()

    def test_reports_every_status(self):
        """Each status prints its own line, reading only the keys it carries."""
        output, _ = self._run(
            [
                {
                    "course_id": "course-v1:org+course+source",
                    "action": ACTION_RESET_ATTEMPTS,
                    "status": STATUS_SUBMITTED,
                    "mapped_problem_id": "block-v1:source",
                    "task_id": "task-1",
                },
                {
                    "course_id": "course-v1:org+course+busy",
                    "action": ACTION_RESET_ATTEMPTS,
                    "status": STATUS_ALREADY_RUNNING,
                    "error": "already running",
                },
                {
                    "course_id": "course-v1:org+course+broken",
                    "action": ACTION_RESET_ATTEMPTS,
                    "status": STATUS_FAILED,
                    "error": "boom",
                },
            ]
        )

        assert "OK | RESET_ATTEMPTS | course-v1:org+course+source" in output
        assert "task=task-1" in output
        assert "SKIP(already running)" in output
        assert "already running" in output
        assert "FAIL" in output
        assert "boom" in output
        # Summary counts one course per status.
        assert "Total courses:      3" in output
        assert "Submitted:          1" in output
        assert "Already running:    1" in output
        assert "Failed:             1" in output

    def test_rescore_output_includes_only_if_higher(self):
        output, mock_submit = self._run(
            [
                {
                    "course_id": COURSE_KEY,
                    "action": ACTION_RESCORE,
                    "status": STATUS_SUBMITTED,
                    "mapped_problem_id": "block-v1:source",
                    "task_id": "task-1",
                    "only_if_higher": True,
                }
            ],
            action=ACTION_RESCORE,
        )

        assert "only_if_higher=True" in output
        # The command defaults only_if_higher on, matching --only-if-higher.
        assert mock_submit.call_args.kwargs["only_if_higher"] is True

    def test_summary_omits_empty_status_lines(self):
        """A clean run reports submitted only, with no other status lines."""
        output, _ = self._run(
            [
                {
                    "course_id": COURSE_KEY,
                    "action": ACTION_RESET_ATTEMPTS,
                    "status": STATUS_SUBMITTED,
                    "mapped_problem_id": "block-v1:source",
                    "task_id": "task-1",
                }
            ]
        )

        assert "Submitted:          1" in output
        assert "Already running:" not in output
        assert "Failed:" not in output
