from django.core.management.base import BaseCommand
from ol_openedx_git_auto_export.models import CourseGitRepo
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview


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

        for course in courses:
            if course.git_url:
                CourseGitRepo.objects.get_or_create(
                    course_id=course.id,
                    defaults={"git_url": course.git_url},
                )
