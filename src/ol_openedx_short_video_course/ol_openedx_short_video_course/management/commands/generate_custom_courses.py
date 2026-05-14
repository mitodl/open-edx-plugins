"""
Management command: generate_custom_courses

Consume a completed CSV mapping file and generate derived course variants.

Workflow:
  1. generate_courses_csv  →  produces a template CSV
  2. Operator edits CSV    →  fills industry code, type, video IDs, changes actions
  3. generate_custom_courses --csv-path <file> --user-email <email>
"""

# ruff: noqa: PLR0912,PLR0915

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
    """Generate derived short-video course variants from a CSV mapping file."""

    help = (
        "Generate derived course variants from one or more source courses "
        "using a CSV mapping file.\n\n"
        "CSV columns: source_course_key, section, subsection, action, "
        "unit display name, industry code, type, video ID\n\n"
        "Actions:\n"
        "  keep   — preserve the subsection exactly as in the source\n"
        "  remove — delete the subsection (empty sections are also removed)\n"
        "  update — replace all units with one video unit "
        "using the given VAL video ID\n\n"
        "One destination course is created per unique "
        "(source_course_key, type, industry code) combination.\n\n"
        "Special: If industry code is 'O' (Original), the generated course key "
        "will not include the industry code (e.g., course-v1:ORG+NUM.TYPE+RUN)."
    )

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--csv-path",
            required=True,
            metavar="PATH",
            help="Path to the completed CSV mapping file",
        )
        parser.add_argument(
            "--user-email",
            required=True,
            metavar="EMAIL",
            help=(
                "Email of the user performing the generation "
                "(for modulestore audit trail)"
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help=(
                "Validate the CSV and display planned operations "
                "without creating any courses"
            ),
        )

    def handle(self, *_args, **options):  # noqa: C901
        """Execute the end-to-end generation flow from the provided CSV."""
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
                treat_industry_code_O_as_original=True,
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
            self.stdout.write(self.style.SUCCESS("Planned operations:\n"))
            for dest_key, ops in result.planned_ops.items():
                self.stdout.write(f"  Destination : {dest_key}")
                self.stdout.write(f"    Source    : {ops['source']}")
                self.stdout.write(f"    Type      : {ops['type']}")
                self.stdout.write(f"    Industry  : {ops['industry']}")
                self.stdout.write(f"    keep      : {ops['actions']['keep']}")
                self.stdout.write(f"    remove    : {ops['actions']['remove']}")
                self.stdout.write(f"    update    : {ops['actions']['update']}")
                self.stdout.write("")
            self.stdout.write(
                self.style.SUCCESS(
                    f"Dry run complete in {result.duration_seconds:.1f}s — "
                    "no changes made."
                )
            )
            return

        # --- Persist per-run records ---
        any_failed = False
        for run_result in result.run_results:
            status = (
                ShortCourseVariant.STATUS_SUCCESS
                if run_result.success
                else ShortCourseVariant.STATUS_FAILED
            )
            tr = run_result.transform_result
            ShortCourseVariant.objects.create(
                batch=batch,
                source_course_key=run_result.source_course_key,
                dest_course_key=run_result.dest_course_key
                if run_result.success
                else None,
                type_code=run_result.type_code,
                industry_code=run_result.industry_code,
                status=status,
                error_log=run_result.error,
                sections_kept=tr.kept if tr else 0,
                sections_removed=tr.removed if tr else 0,
                sections_updated=tr.updated if tr else 0,
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
        col_w = 58
        self.stdout.write(
            self.style.SUCCESS(
                f"\n{'Destination':<{col_w}} {'Keep':>6} {'Remove':>8} "
                f"{'Update':>8}  Status"
            )
        )
        self.stdout.write("-" * (col_w + 32))

        for run_result in result.run_results:
            tr = run_result.transform_result
            kept = tr.kept if tr else 0
            removed = tr.removed if tr else 0
            updated = tr.updated if tr else 0
            if run_result.success:
                status_str = "OK"
            else:
                status_str = f"FAILED: {run_result.error[:35]}"

            self.stdout.write(
                f"{run_result.dest_course_key:<{col_w}} {kept:>6} {removed:>8} "
                f"{updated:>8}  {status_str}"
            )

        elapsed = result.duration_seconds
        self.stdout.write(self.style.SUCCESS(f"\nCompleted in {elapsed:.1f}s."))

        if any_failed:
            msg = (
                "One or more course variants failed to generate. "
                "See the summary above for details."
            )
            raise CommandError(msg)
