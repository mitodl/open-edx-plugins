"""
Management command: generate_custom_courses

Read a CSV mapping file and create new courses in the Open edX platform.

CSV format (header row required):
  course_name,course_key,section_name,subsection_name,vertical_name,edx_video_id

Each unique course_key produces one new course.  Rows for the same course_key
are grouped and used to build sections → subsections → units → video blocks in
the order they appear in the CSV.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from ol_openedx_short_video_course.models import (
    ShortCourseCreationJob,
    ShortCourseVariant,
)
from ol_openedx_short_video_course.services import generate_custom_courses

log = logging.getLogger(__name__)
User = get_user_model()


class Command(BaseCommand):
    """Create new short-video courses from a CSV mapping file."""

    help = (
        "Read a CSV file and create one new course per unique course_key.\n\n"
        "CSV columns: course_name, course_key, section_name, subsection_name, "
        "vertical_name, edx_video_id\n\n"
        "For each course, sections, subsections, units, and video blocks are "
        "created in the order they appear in the CSV.\n\n"
        "Use --dry-run to validate the CSV and preview the planned structure "
        "without writing anything to the platform."
    )

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--csv-path",
            required=True,
            metavar="PATH",
            help="Path to the CSV mapping file",
        )
        parser.add_argument(
            "--user-email",
            required=True,
            metavar="EMAIL",
            help="Email of the user performing the creation (for audit trail)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Validate the CSV and display the planned course structure "
                "without creating anything"
            ),
        )

    def handle(self, *_args, **options):  # noqa: C901,PLR0912,PLR0915
        """Execute the course-creation flow from the provided CSV."""
        csv_path: str = options["csv_path"]
        user_email: str = options["user_email"]
        dry_run: bool = options["dry_run"]

        # Resolve user
        try:
            user = User.objects.get(email=user_email)
        except User.DoesNotExist:
            msg = (
                f"No user found with email '{user_email}'. "
                "Create the user first or use a different email."
            )
            raise CommandError(msg) from None

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN — validation only, no courses will be created\n"
                )
            )

        # Persist batch record (skip in dry-run)
        batch: ShortCourseCreationJob | None = None
        if not dry_run:
            batch = ShortCourseCreationJob.objects.create(
                csv_path=csv_path,
                run_by_email=user_email,
                status=ShortCourseCreationJob.STATUS_RUNNING,
            )

        # Run the service
        try:
            result = generate_custom_courses(
                csv_path=csv_path,
                user_id=user.id,
                dry_run=dry_run,
            )
        except Exception as exc:
            if batch:
                batch.status = ShortCourseCreationJob.STATUS_FAILED
                batch.error_summary = str(exc)
                batch.save()
            msg = f"Unexpected error: {exc}"
            raise CommandError(msg) from exc

        # --- Validation failure path ---
        if result.validation_errors:
            self.stderr.write(self.style.ERROR("\nValidation errors:"))
            for err in result.validation_errors:
                self.stderr.write(self.style.ERROR(f"  • {err}"))
            if batch:
                batch.status = ShortCourseCreationJob.STATUS_FAILED
                batch.error_summary = "\n".join(result.validation_errors)
                batch.save()
            msg = (
                "\nValidation failed — no courses were created. "
                "Correct the errors above and retry."
            )
            raise CommandError(msg)

        # --- Dry-run output ---
        if dry_run:
            self.stdout.write(self.style.SUCCESS("Planned courses:\n"))
            for course_key_str, plan in result.planned_ops.items():
                self.stdout.write(f"  Course key : {course_key_str}")
                self.stdout.write(f"  Name       : {plan['course_name']}")
                self.stdout.write(f"  Units      : {plan['total_units']}")
                for sec, subs in plan["sections"].items():
                    self.stdout.write(f"    Section  : {sec}")
                    for sub in subs:
                        self.stdout.write(f"      Subsection: {sub}")
                self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete in {result.duration_seconds:.1f}s — "
                    "no changes made."
                )
            )
            return

        # --- Persist per-course records and print summary ---
        any_failed = False
        for run_result in result.run_results:
            status = (
                ShortCourseVariant.STATUS_SUCCESS
                if run_result.success
                else ShortCourseVariant.STATUS_FAILED
            )
            stats = run_result.stats
            ShortCourseVariant.objects.create(
                batch=batch,
                course_name=run_result.course_name,
                dest_course_key=run_result.course_key_str
                if run_result.success
                else None,
                status=status,
                error_log=run_result.error,
                sections_created=stats.sections if stats else 0,
                subsections_created=stats.subsections if stats else 0,
                units_created=stats.units if stats else 0,
            )
            if not run_result.success:
                any_failed = True

        # Update batch status
        if batch:
            if any_failed:
                success_count = sum(1 for r in result.run_results if r.success)
                batch.status = (
                    ShortCourseCreationJob.STATUS_PARTIAL
                    if success_count > 0
                    else ShortCourseCreationJob.STATUS_FAILED
                )
            else:
                batch.status = ShortCourseCreationJob.STATUS_SUCCESS
            batch.save()

        # --- Summary table ---
        col_w = 55
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'Course Key':<{col_w}} {'Sec':>4} {'Sub':>4} {'Units':>6}  Status"
            )
        )
        self.stdout.write("-" * (col_w + 24))

        for run_result in result.run_results:
            stats = run_result.stats
            if run_result.success:
                status_str = "OK"
            else:
                status_str = f"FAILED: {run_result.error[:30]}"
            self.stdout.write(
                f"{run_result.course_key_str:<{col_w}} "
                f"{(stats.sections if stats else 0):>4} "
                f"{(stats.subsections if stats else 0):>4} "
                f"{(stats.units if stats else 0):>6}  "
                f"{status_str}"
            )

        self.stdout.write(
            self.style.SUCCESS(f"\nCompleted in {result.duration_seconds:.1f}s.")
        )

        if any_failed:
            msg = (
                "One or more courses failed to be created. "
                "See the summary above for details."
            )
            raise CommandError(msg)
