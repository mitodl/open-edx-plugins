"""
Django management command for migrating git URLs
from course advance settings to CourseGitHubRepository model.

This command scans existing courses in the modulestore for git URLs and migrates them
to the CourseGitHubRepository model. It handles duplicate git URLs by creating new
GitHub repositories for courses that would otherwise share the same repository.

Usage:
    python manage.py migrate_giturl [course_id1] [course_id2] ...

Examples:
    # Migrate all courses
    python manage.py migrate_giturl

    # Migrate specific courses
    python manage.py migrate_giturl course-v1:MITx+6.00x+2T2024

The command will:
1. Query all courses (or specified courses) from CourseOverview
2. Extract git URLs from the course modulestore data
3. Create CourseGitHubRepository records for courses with git URLs
4. Handle duplicate git URLs by creating new GitHub repositories
5. Report on courses without git URLs

This is typically run as a one-time migration when setting up the git auto-export plugin
or when consolidating existing course git configurations.
"""

from django.core.management.base import BaseCommand
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.models import CourseGitHubRepository
from ol_openedx_git_auto_export.tasks import async_create_github_repo


class Command(BaseCommand):
    help = """
    Migrate git URL from course(s) advanced settings to CourseGitHubRepository model
    """

    def add_arguments(self, parser):
        parser.add_argument(
            "course_keys",
            nargs="*",
            type=str,
            help="List of course keys to migrate their giturl",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        course_keys = options.get("course_keys", [])
        courses = CourseOverview.objects.all().order_by("created")
        if course_keys:
            courses = courses.filter(id__in=course_keys)
        seen_giturls = set()
        for course in courses:
            course_module = modulestore().get_course(course.id, depth=1)
            giturl = course_module.giturl
            if giturl and giturl not in seen_giturls:
                seen_giturls.add(giturl)
                self.stdout.write(
                    self.style.SUCCESS(f"Course {course.id} has giturl: {giturl}")
                )
                CourseGitHubRepository.objects.get_or_create(
                    course_key=course.id,
                    defaults={"git_url": giturl},
                )
                continue

            if giturl and giturl in seen_giturls:
                self.stdout.write(
                    self.style.WARNING(
                        f"Course {course.id} has a duplicate giturl: {giturl}\n"
                        f"Creating a new GitHub repository for {course.id}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"Course {course.id} does not have a giturl.\n"
                        "Creating a new GitHub repository..."
                    )
                )

            async_create_github_repo.delay(str(course.id), export_course=True)
            self.stdout.write(
                self.style.SUCCESS(
                    f"Triggered async GitHub repository creation for course {course.id}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Git URLs migrated successfully."))
