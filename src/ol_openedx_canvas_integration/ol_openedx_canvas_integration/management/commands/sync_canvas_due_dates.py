"""
Script for syncing Canvas due dates with Open edX
"""

import logging
from pathlib import Path

from django.core.management.base import BaseCommand
from openedx.core.djangoapps.content.course_overviews.models import CourseOverview

from ol_openedx_canvas_integration.cms_tasks import sync_canvas_due_dates

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Sync Canvas due dates with Open edX
    """

    help = "Sync Canvas due dates with Open edX"

    def add_arguments(self, parser):
        parser.add_argument(
            "course_keys",
            nargs="*",
            type=str,
            help="List of courses to sync due dates",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Sync all courses in the system",
        )

    def handle(self, *args, **options):  # noqa: ARG002
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

        courses = (
            CourseOverview.objects.all()
            .order_by("created")
            .values_list("id", flat=True)
        )
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
        for course_id in courses:
            try:
                sync_canvas_due_dates.delay(str(course_id))
            except Exception as ex:  # noqa: BLE001
                self.stderr.write(
                    self.style.ERROR(f"Error processing course {course_id}: {ex!s}")
                )
