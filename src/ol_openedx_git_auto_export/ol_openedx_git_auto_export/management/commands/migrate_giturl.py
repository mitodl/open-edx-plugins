"""
Django management command for migrating git URLs
from course advance settings to CourseGitRepository model.

This command scans existing courses in the modulestore for git URLs and migrates them
to the CourseGitRepository model. It handles duplicate git URLs by creating new
GitHub repositories for courses that would otherwise share the same repository.

Usage:
    python manage.py migrate_giturl [course_id1] [course_id2] ...
    python manage.py migrate_giturl --all

Examples:
    # Migrate all courses
    python manage.py migrate_giturl --all

    # Migrate specific courses
    python manage.py migrate_giturl course-v1:MITx+6.00x+2T2024

The command will:
1. Query all courses (or specified courses) from CourseOverview
2. Extract git URLs from the course modulestore data
3. Create CourseGitRepository records for courses with git URLs
4. Handle duplicate git URLs by creating new GitHub repositories
5. Create new GitHub repositories for courses without git URLs

This is typically run as a one-time migration when setting up the git auto-export plugin
or when consolidating existing course git configurations.
"""

import time
from pathlib import Path

from celery import group
from django.core.management.base import BaseCommand
from ol_openedx_git_auto_export.models import CourseGitRepository
from ol_openedx_git_auto_export.tasks import (
    async_create_github_repo,
)
from ol_openedx_git_auto_export.utils import is_auto_repo_creation_enabled
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore


class Command(BaseCommand):
    help = """
    Migrate git URL from course(s) advanced settings to CourseGitRepository model
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "course_keys",
            nargs="*",
            type=str,
            help="List of course keys to migrate their giturl",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Migrate all courses in the system",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        if not is_auto_repo_creation_enabled():
            return

        course_keys = options.get("course_keys", [])
        all_courses = options.get("all")

        if not course_keys and not all_courses:
            # Either course_keys or --all flag must be provided
            command_name = Path(__file__).stem
            self.stderr.write(
                self.style.ERROR(
                    "Error: You must specify either course keys or use the --all flag.\n"  # noqa: E501
                    "Examples:\n"
                    f"  python manage.py {command_name} --all\n"
                    f"  python manage.py {command_name} course-v1:MITx+6.00x+2T2024"
                )
            )
            return

        # Both course_keys and --all flag cannot be used together
        if course_keys and all_courses:
            self.stderr.write(
                self.style.ERROR(
                    "Error: Cannot use both course keys and --all flag together. "
                    "Please use one or the other."
                )
            )
            return

        courses = CourseOverview.objects.all().order_by("created")
        if course_keys:
            courses = courses.filter(id__in=course_keys)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processing {len(course_keys)} specified course(s)..."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Processing all {courses.count()} course(s) in the system..."
                )
            )

        migration_logs = {
            "existing_repos": [],
            "duplicate_repos": [],
            "new_repos_success": [],
            "new_repos_failed": [],
            "no_giturl": [],
        }

        processed_giturls = set()
        repos_to_create = []
        for course in courses:
            course_module = modulestore().get_course(course.id, depth=1)
            giturl = course_module.giturl

            if not giturl:
                migration_logs["no_giturl"].append({"course_id": str(course.id)})
            elif giturl not in processed_giturls:
                processed_giturls.add(giturl)
                migration_logs["existing_repos"].append(
                    {"course_id": str(course.id), "giturl": giturl}
                )
                CourseGitRepository.objects.get_or_create(
                    course_key=course.id,
                    defaults={"git_url": giturl},
                )
                continue
            elif giturl in processed_giturls:
                migration_logs["duplicate_repos"].append(
                    {"course_id": str(course.id), "duplicate_giturl": giturl}
                )

            repos_to_create.append(course.id)

        if repos_to_create:
            self.stdout.write(f"Processing repository creation for {course.id}...")
            self._process_repositories_in_parallel(repos_to_create, migration_logs)

        self._display_migration_summary(migration_logs)

    def _process_repositories_in_parallel(self, repos_to_create, migration_logs):
        """
        Process repository creation in parallel for better resource management.

        Args:
            repos_to_create (list): List of course IDs that need repositories
            migration_logs (dict): Dictionary to store migration results
        """
        total_repos = len(repos_to_create)
        self.stdout.write(f"Processing {total_repos} repositories in parallel...")

        # Create group of tasks for all repositories
        job = group(
            async_create_github_repo.s(str(course_id), export_course=True)
            for course_id in repos_to_create
        )

        # Execute batch in parallel
        group_result = job.apply_async()

        # Monitor progress for this batch
        self._monitor_group_progress(group_result, len(repos_to_create))

        batch_results = group_result.get(propagate=False)

        # Process results for this batch
        self._process_batch_results(repos_to_create, batch_results, migration_logs)

    def _process_batch_results(self, course_ids, results, migration_logs):
        """
        Process the results from a batch of repository creation tasks.

        Args:
            course_ids (list): List of course IDs in this batch
            results (list): Results from the Celery group execution
            migration_logs (dict): Dictionary to store migration results
        """
        for i, result in enumerate(results):
            course_id = course_ids[i]
            course_module = modulestore().get_course(course_id, depth=1)
            giturl = course_module.giturl if course_module else None

            # Handle individual task results or exceptions
            if isinstance(result, Exception):
                migration_logs["new_repos_failed"].append(
                    {
                        "course_id": str(course_id),
                        "reason": f"Task failed with exception: {result!s}",
                    }
                )
            elif isinstance(result, tuple):
                is_success, response_msg = result
                if is_success:
                    migration_logs["new_repos_success"].append(
                        {
                            "course_id": str(course_id),
                            "ssh_url": response_msg,
                            "reason": "duplicate_giturl" if giturl else "no_giturl",
                        }
                    )
                else:
                    migration_logs["new_repos_failed"].append(
                        {"course_id": str(course_id), "reason": response_msg}
                    )
            else:
                migration_logs["new_repos_failed"].append(
                    {
                        "course_id": str(course_id),
                        "reason": f"Unexpected result format: {result}",
                    }
                )

    def _monitor_group_progress(self, group_result, total_tasks):
        """
        Monitor the progress of parallel task execution.

        Args:
            group_result: The GroupResult object from Celery
            total_tasks (int): Total number of tasks in the group
        """
        if total_tasks <= 1:
            return  # Skip monitoring for single tasks

        self.stdout.write("Monitoring task progress...")
        last_completed = 0

        while not group_result.ready():
            completed = sum(1 for task in group_result.children if task.ready())

            if completed != last_completed:
                progress_percent = (completed / total_tasks) * 100
                self.stdout.write(
                    f"Progress: {completed}/{total_tasks} tasks completed ({progress_percent:.1f}%)"  # noqa: E501
                )
                last_completed = completed

            time.sleep(1)  # Check progress every second

        self.stdout.write(f"✅ All {total_tasks} tasks completed!")

    def _display_migration_summary(self, logs):
        """
        Display a comprehensive summary of the migration results.

        Args:
            logs (dict): Dictionary containing categorized migration results
        """
        self.stdout.write("\n" + "=" * 80)
        self.stdout.write(self.style.SUCCESS("GIT URL MIGRATION SUMMARY"))
        self.stdout.write("=" * 80)

        # Summary statistics
        total_existing = len(logs["existing_repos"])
        total_duplicates = len(logs["duplicate_repos"])
        total_no_giturl = len(logs["no_giturl"])
        total_new_success = len(logs["new_repos_success"])
        total_new_failed = len(logs["new_repos_failed"])
        total_processed = total_existing + total_duplicates + total_no_giturl

        self.stdout.write("\n📊 STATISTICS:")
        self.stdout.write(f"  Total courses processed: {total_processed}")
        self.stdout.write(f"  Existing repositories: {total_existing}")
        self.stdout.write(f"  Duplicate git URLs: {total_duplicates}")
        self.stdout.write(f"  Courses without git URLs: {total_no_giturl}")
        self.stdout.write(f"  New repositories created: {total_new_success}")
        self.stdout.write(f"  Failed repository creations: {total_new_failed}")

        self.display_migration_section(
            "\n✅ EXISTING REPOSITORIES",
            logs["existing_repos"],
            "existing",
            self.style.SUCCESS,
        )

        self.display_migration_section(
            "\n🆕 NEW REPOSITORIES CREATED",
            logs["new_repos_success"],
            "success",
            self.style.SUCCESS,
        )

        self.display_migration_section(
            "\n❌ FAILED REPOSITORY CREATIONS",
            logs["new_repos_failed"],
            "failed",
            self.style.ERROR,
        )

        self.display_migration_section(
            "\n⚠️ DUPLICATE GIT URLs HANDLED",
            logs["duplicate_repos"],
            "duplicate",
            self.style.WARNING,
        )

    def display_migration_section(self, title, repo_stats, message_type, style_fn):
        """
        Display a section of migration results with consistent formatting.

        Args:
            title (str): Title for the section (e.g., "EXISTING REPOSITORIES")
            repo_stats (list): List of repository data dictionaries
            message_type (str): Type of message to display (e.g., "existing", "success")
            style_fn (callable): Function to apply styling to the output
        """
        if not repo_stats:
            return

        message_formats = {
            "existing": lambda data: f"  • {data['course_id']}: {data['giturl']}",
            "success": lambda data: f"  • {data['course_id']}: {data['ssh_url']} (reason: {data['reason']})",  # noqa: E501
            "failed": lambda data: f"  • {data['course_id']}: Creation failed (reason: {data['reason']})",  # noqa: E501
            "duplicate": lambda data: f"  • {data['course_id']}: Had duplicate URL {data['duplicate_giturl']}",  # noqa: E501
        }

        count = len(repo_stats)
        self.stdout.write(f"\n{title} ({count}):")
        for repo in repo_stats:
            message = message_formats[message_type](repo)
            self.stdout.write(style_fn(message))
