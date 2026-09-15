"""
Management command to reset attempts or rescore problem for synced courses.

Resets attempts or rescores learners for a problem across all courses in a sync mapping
(source course and all target courses).

Usage:
    python manage.py lms sync_problem_actions <action> \
    <source_course_key> <problem_id> [OPTIONS]

Actions:
    reset_attempts: Resets learner attempts for a problem
    rescore: Rescores learner for a problem

Options:
    --username USERNAME
        Username to run the task as (default: 'courses_service_worker')
    --only-if-higher / --no-only-if-higher
        Whether to rescore only if the new score is higher (default: True)

Examples:
    python manage.py lms sync_problem_actions reset_attempts \
        "course-v1:ORG+COURSE+RUN" \
        "block-v1:ORG+COURSE+RUN+type@problem+block@abc123" \
        --username courses_service_worker

    python manage.py lms sync_problem_actions rescore \
        "course-v1:ORG+COURSE+RUN" \
        "block-v1:ORG+COURSE+RUN+type@problem+block@abc123" \
        --username courses_service_worker \
        --only-if-higher
"""

import argparse

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.test.client import RequestFactory
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey

from ol_openedx_course_sync.constants import (
    ACTION_RESCORE,
    STATUS_ALREADY_RUNNING,
    STATUS_FAILED,
    STATUS_SUBMITTED,
    VALID_ACTIONS,
)
from ol_openedx_course_sync.utils import submit_problem_action_for_synced_courses

User = get_user_model()


class Command(BaseCommand):
    """
    Reset attempts or rescore problem for all synced courses.
    """

    help = "Reset attempts or rescore problem across all synced courses"

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            "action",
            type=str,
            choices=VALID_ACTIONS,
            help="Action to perform: 'reset_attempts' or 'rescore'",
        )
        parser.add_argument(
            "source_course_key",
            type=str,
            help="Source course key (e.g., 'course-v1:ORG+COURSE+RUN')",
        )
        parser.add_argument(
            "problem_id",
            type=str,
            help=(
                "Problem usage key "
                "(e.g., 'block-v1:ORG+COURSE+RUN+type@problem+block@id')"
            ),
        )
        parser.add_argument(
            "--username",
            type=str,
            default="courses_service_worker",
            help="Username to run the task as (default: 'courses_service_worker')",
        )
        parser.add_argument(
            "--only-if-higher",
            action=argparse.BooleanOptionalAction,
            default=True,
            help=(
                "Whether to rescore only if the new score is higher "
                "(default: True, use --no-only-if-higher to disable)"
            ),
        )

    def handle(self, **options):
        """Execute the command."""
        action = options["action"]
        source_course_key_str = options["source_course_key"]
        problem_id_str = options["problem_id"]
        username = options["username"]
        only_if_higher = options["only_if_higher"]

        try:
            source_course_key = CourseKey.from_string(source_course_key_str)
        except InvalidKeyError as exc:
            error_msg = f"Invalid source course key: {source_course_key_str}"
            raise CommandError(error_msg) from exc

        try:
            problem_usage_key = UsageKey.from_string(problem_id_str)
        except InvalidKeyError as exc:
            error_msg = f"Invalid problem usage key: {problem_id_str}"
            raise CommandError(error_msg) from exc

        try:
            request_obj = self._make_shell_request(username)
        except User.DoesNotExist as exc:
            error_msg = f"User not found: {username}"
            raise CommandError(error_msg) from exc

        results = submit_problem_action_for_synced_courses(
            request_obj,
            source_course_key,
            problem_usage_key,
            action,
            only_if_higher=only_if_higher,
        )

        self._print_results(results)
        self._print_summary(results, action)

    def _make_shell_request(self, username):
        """
        Create a request object for shell execution.

        Args:
            username: Username to associate with the request

        Returns:
            Request object with user context

        Raises:
            User.DoesNotExist: If user not found
        """
        user = User.objects.get(username=username)
        req = RequestFactory().post(
            "/shell/instructor-task",
            HTTP_USER_AGENT="lms-shell",
            REMOTE_ADDR="127.0.0.1",
            SERVER_NAME="localhost",
        )
        req.user = user
        return req

    def _print_results(self, results):
        """Print one line per course."""
        for row in results:
            action = row["action"]
            course_id = row["course_id"]

            if row["status"] == STATUS_SUBMITTED:
                message = (
                    f"OK | {action.upper()} | {course_id} | {row['mapped_problem_id']}"
                )
                if action == ACTION_RESCORE:
                    message += f" | only_if_higher={row['only_if_higher']}"
                self.stdout.write(f"{message} | task={row['task_id']}")
            elif row["status"] == STATUS_ALREADY_RUNNING:
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP(already running) | {action} | {course_id} "
                        f"| {row['error']}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.ERROR(f"FAIL | {action} | {course_id} | {row['error']}")
                )

    def _print_summary(self, results, action):
        """Print summary of operation."""
        submitted = sum(1 for r in results if r["status"] == STATUS_SUBMITTED)
        already_running = sum(
            1 for r in results if r["status"] == STATUS_ALREADY_RUNNING
        )
        failed = sum(1 for r in results if r["status"] == STATUS_FAILED)

        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(f"{action.upper()} Summary")
        self.stdout.write("=" * 50)
        self.stdout.write(f"Total courses:      {len(results)}")
        self.stdout.write(self.style.SUCCESS(f"Submitted:          {submitted}"))
        if already_running:
            self.stdout.write(
                self.style.WARNING(f"Already running:    {already_running}")
            )
        if failed:
            self.stdout.write(self.style.ERROR(f"Failed:             {failed}"))
        self.stdout.write("=" * 50)
