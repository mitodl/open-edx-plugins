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

from django.core.management.base import BaseCommand
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.models import CourseGitRepository
from ol_openedx_git_auto_export.tasks import (
    async_create_github_repo,
)
from ol_openedx_git_auto_export.utils import is_auto_repo_creation_enabled


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
        all_courses = options.get("all", False)

        # Either course_keys or --all flag must be provided
        if not course_keys and not all_courses:
            self.stderr.write(
                self.style.ERROR(
                    "Error: You must specify either course keys or use the --all flag.\n"  # noqa: E501
                    "Examples:\n"
                    "  python manage.py migrate_giturl --all\n"
                    "  python manage.py migrate_giturl course-v1:MITx+6.00x+2T2024"
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
        for course in courses:
            course_module = modulestore().get_course(course.id, depth=1)
            giturl = course_module.giturl

            if giturl and giturl not in processed_giturls:
                processed_giturls.add(giturl)
                migration_logs["existing_repos"].append(
                    {"course_id": str(course.id), "giturl": giturl}
                )
                CourseGitRepository.objects.get_or_create(
                    course_key=course.id,
                    defaults={"git_url": giturl},
                )
                continue

            if giturl and giturl in processed_giturls:
                migration_logs["duplicate_repos"].append(
                    {"course_id": str(course.id), "duplicate_giturl": giturl}
                )
            else:
                migration_logs["no_giturl"].append({"course_id": str(course.id)})

            # Create new repository for courses with duplicate or no giturl
            self.stdout.write(f"Processing repository creation for {course.id}...")
            task = async_create_github_repo.delay(str(course.id), export_course=True)
            is_success, response_msg = task.get()

            if is_success:
                migration_logs["new_repos_success"].append(
                    {
                        "course_id": str(course.id),
                        "ssh_url": response_msg,
                        "reason": "duplicate_giturl" if giturl else "no_giturl",
                    }
                )
            else:
                migration_logs["new_repos_failed"].append(
                    {"course_id": str(course.id), "reason": response_msg}
                )

        self._display_migration_summary(migration_logs)

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

        # Existing repositories
        if logs["existing_repos"]:
            self.stdout.write(f"\n✅ EXISTING REPOSITORIES ({total_existing}):")
            for repo in logs["existing_repos"]:
                self.stdout.write(
                    self.style.SUCCESS(f"  • {repo['course_id']}: {repo['giturl']}")
                )

        # Successfully created repositories
        if logs["new_repos_success"]:
            self.stdout.write(f"\n🆕 NEW REPOSITORIES CREATED ({total_new_success}):")
            for repo in logs["new_repos_success"]:
                msg = f"  • {repo['course_id']}: {repo['ssh_url']} (reason: {repo['reason']})"  # noqa: E501
                self.stdout.write(self.style.SUCCESS(msg))

        # Failed repository creations
        if logs["new_repos_failed"]:
            self.stdout.write(f"\n❌ FAILED REPOSITORY CREATIONS ({total_new_failed}):")
            for repo in logs["new_repos_failed"]:
                msg = f"  • {repo['course_id']}: Creation failed (reason: {repo['reason']})"  # noqa: E501
                self.stdout.write(self.style.ERROR(msg))

        # Duplicate git URLs
        if logs["duplicate_repos"]:
            self.stdout.write(f"\n⚠️  DUPLICATE GIT URLs HANDLED ({total_duplicates}):")
            for repo in logs["duplicate_repos"]:
                msg = f"  • {repo['course_id']}: Had duplicate URL {repo['duplicate_giturl']}"  # noqa: E501
                self.stdout.write(self.style.WARNING(msg))

        # Final status
        self.stdout.write("\n" + "=" * 80)
        if total_new_failed == 0:
            self.stdout.write(
                self.style.SUCCESS("✅ GIT URL MIGRATION COMPLETED SUCCESSFULLY!")
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  GIT URL MIGRATION COMPLETED WITH {total_new_failed} FAILURES!"
                )
            )
        self.stdout.write("=" * 80 + "\n")
