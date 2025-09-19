from django.core.management.base import BaseCommand
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview
from xmodule.modulestore.django import modulestore

from ol_openedx_git_auto_export.models import CourseGitRepo
from ol_openedx_git_auto_export.utils import create_github_repo


class Command(BaseCommand):
    help = "Migrate git URLs from courses to CourseGitRepo model"

    def add_arguments(self, parser):
        parser.add_argument(
            "course_ids",
            nargs="*",
            type=str,
            help="List of course IDs to migrate their giturl",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        course_ids = options.get("course_ids")
        courses = CourseOverview.objects.all()
        if course_ids:
            courses = courses.filter(id__in=course_ids)
        seen_giturls = set()
        for course in courses:
            course_module = modulestore().get_course(course.id, depth=1)
            giturl = course_module.giturl
            if giturl and giturl not in seen_giturls:
                seen_giturls.add(giturl)
                self.stdout.write(
                    self.style.SUCCESS(f"Course {course.id} has giturl: {giturl}")
                )
                CourseGitRepo.objects.get_or_create(
                    course_id=course.id,
                    defaults={"git_url": giturl},
                )
            elif giturl and giturl in seen_giturls:
                self.stdout.write(
                    self.style.WARNING(
                        f"Course {course.id} has a duplicate giturl: {giturl}\n"
                        f"Creating a new GitHub repository for {course.id}"
                    )
                )
                ssh_url = create_github_repo(course.id)
                if ssh_url:
                    seen_giturls.add(ssh_url)
            else:
                self.stdout.write(
                    self.style.WARNING(f"Course {course.id} does not have a giturl.")
                )

        self.stdout.write(self.style.SUCCESS("Git URLs migrated successfully."))
