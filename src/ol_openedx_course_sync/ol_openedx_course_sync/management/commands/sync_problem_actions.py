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
        Username to run the task as (default: 'studio_worker')
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
from lms.djangoapps.instructor_task import api as task_api
from lms.djangoapps.instructor_task.api_helper import AlreadyRunningError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from xmodule.modulestore.exceptions import ItemNotFoundError

from ol_openedx_course_sync.utils import get_syncable_course_mappings

User = get_user_model()

ACTION_RESET_ATTEMPTS = "reset_attempts"
ACTION_RESCORE = "rescore"
VALID_ACTIONS = [ACTION_RESET_ATTEMPTS, ACTION_RESCORE]

STATUS_SUBMITTED = "submitted"
STATUS_ALREADY_RUNNING = "already_running"
STATUS_FAILED = "failed"


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
            default="studio_worker",
            help="Username to run the task as (default: 'studio_worker')",
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
            # Validate source course key
            source_course_key = CourseKey.from_string(source_course_key_str)
        except InvalidKeyError as exc:
            error_msg = f"Invalid source course key: {source_course_key_str}"
            raise CommandError(error_msg) from exc

        try:
            # Validate problem ID
            problem_usage_key = UsageKey.from_string(problem_id_str)
        except InvalidKeyError as exc:
            error_msg = f"Invalid problem usage key: {problem_id_str}"
            raise CommandError(error_msg) from exc

        # Get all courses for this sync mapping
        courses = self._get_synced_courses(source_course_key)
        if not courses:
            error_msg = (
                f"No sync mappings found for source course: {source_course_key_str}"
            )
            raise CommandError(error_msg)

        # Create request object
        try:
            request_obj = self._make_shell_request(username)
        except User.DoesNotExist as exc:
            error_msg = f"User not found: {username}"
            raise CommandError(error_msg) from exc

        # Process action for all courses
        if action == ACTION_RESET_ATTEMPTS:
            results = self._submit_for_courses(
                request_obj, courses, problem_usage_key, ACTION_RESET_ATTEMPTS
            )
        else:  # rescore
            results = self._submit_for_courses(
                request_obj,
                courses,
                problem_usage_key,
                ACTION_RESCORE,
                only_if_higher=only_if_higher,
            )

        # Print summary
        self._print_summary(results, action)

    def _get_synced_courses(self, source_course_key):
        """
        Get all courses for a sync mapping (source + all targets).

        Args:
            source_course_key: CourseKey of the source course

        Returns:
            List of course key strings
        """
        courses = [str(source_course_key)]

        # Get all target courses for this source using the utility function
        mappings = get_syncable_course_mappings(source_course_key)

        if mappings:
            courses.extend(str(mapping.target_course) for mapping in mappings)

        return courses

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

    def _submit_for_courses(
        self,
        request,
        courses,
        problem_usage_key,
        action,
        *,
        only_if_higher=False,
    ):
        """
        Submit reset/rescore tasks for courses.

        Args:
            request: Request object with user context
            courses: List of course key strings
            problem_usage_key: UsageKey of the problem
            action: Action to perform (reset_attempts or rescore)
            only_if_higher: Only rescore if new score is higher (rescore only)

        Returns:
            List of result dictionaries
        """
        results = []

        for course_id_str in courses:
            try:
                course_key = CourseKey.from_string(course_id_str)
                mapped_problem_key = problem_usage_key.map_into_course(course_key)

                if action == ACTION_RESET_ATTEMPTS:
                    task = task_api.submit_reset_problem_attempts_for_all_students(
                        request, mapped_problem_key
                    )
                else:  # rescore
                    task = task_api.submit_rescore_problem_for_all_students(
                        request, mapped_problem_key, only_if_higher=only_if_higher
                    )

                row = {
                    "course_id": course_id_str,
                    "action": action,
                    "mapped_problem_id": str(mapped_problem_key),
                    "task_id": task.task_id,
                    "status": STATUS_SUBMITTED,
                }
                if action == ACTION_RESCORE:
                    row["only_if_higher"] = only_if_higher

                results.append(row)
                if action == ACTION_RESET_ATTEMPTS:
                    self.stdout.write(
                        "OK | "
                        f"{action.upper()} | {course_id_str} | {mapped_problem_key} "
                        f"| task={task.task_id}"
                    )
                else:  # rescore
                    self.stdout.write(
                        "OK | "
                        f"{action.upper()} | {course_id_str} | {mapped_problem_key} "
                        f"| only_if_higher={only_if_higher} | task={task.task_id}"
                    )

            except AlreadyRunningError as exc:
                row = {
                    "course_id": course_id_str,
                    "action": action,
                    "status": STATUS_ALREADY_RUNNING,
                    "error": str(exc),
                }
                results.append(row)
                self.stdout.write(
                    self.style.WARNING(
                        f"SKIP(already running) | {action} | {course_id_str} | {exc}"
                    )
                )

            except (InvalidKeyError, ItemNotFoundError, ValueError) as exc:
                row = {
                    "course_id": course_id_str,
                    "action": action,
                    "status": STATUS_FAILED,
                    "error": str(exc),
                }
                results.append(row)
                self.stdout.write(
                    self.style.ERROR(f"FAIL | {action} | {course_id_str} | {exc}")
                )

            except Exception as exc:  # pylint: disable=broad-except  # noqa: BLE001
                row = {
                    "course_id": course_id_str,
                    "action": action,
                    "status": STATUS_FAILED,
                    "error": str(exc),
                }
                results.append(row)
                self.stdout.write(
                    self.style.ERROR(f"FAIL | {action} | {course_id_str} | {exc}")
                )

        return results

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
