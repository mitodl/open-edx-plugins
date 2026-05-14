"""
Management command: generate_courses_csv

Walk one or more source courses and emit an 8-column CSV template pre-filled
with ``keep`` actions and subsection display names.  Operators complete the
``industry code``, ``type``, and ``video ID`` columns, then change actions to
``remove`` or ``update`` as needed before running ``generate_custom_courses``.
"""

import csv
import logging
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils.csv_parser import CSV_HEADER

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Generate a CSV template from one or more source courses."""

    help = (
        "Walk each source course and emit an 8-column CSV template.\n\n"
        "Columns: source_course_key, section, subsection, action, "
        "unit display name, industry code, type, video ID\n\n"
        "All rows are pre-filled with action=keep and the subsection display "
        "name.  Fill in 'industry code', 'type', and 'video ID' before "
        "running generate_custom_courses."
    )

    def add_arguments(self, parser):
        """Add command-line arguments."""
        parser.add_argument(
            "--source-course-keys",
            nargs="+",
            required=True,
            metavar="COURSE_KEY",
            help="One or more source course keys (e.g. course-v1:ORG+NUM+RUN)",
        )
        parser.add_argument(
            "--output-path",
            required=True,
            metavar="PATH",
            help="File path for the generated CSV template",
        )

    def handle(self, *_args, **options):
        """Generate and write a CSV template for provided source courses."""
        from xmodule.modulestore.django import modulestore  # noqa: PLC0415

        source_key_strs: list[str] = options["source_course_keys"]
        output_path: str = options["output_path"]

        store = modulestore()
        rows: list[list[str]] = []
        errors: list[str] = []

        for key_str in source_key_strs:
            try:
                course_key = CourseKey.from_string(key_str)
            except InvalidKeyError:
                errors.append(f"Invalid course key: '{key_str}'")
                continue

            course = store.get_course(course_key, depth=4)
            if course is None:
                errors.append(f"Course not found: '{key_str}'")
                continue

            section_count = 0
            subsection_count = 0

            for section in course.get_children():
                section_key = str(section.location)
                for subsection in section.get_children():
                    subsection_key = str(subsection.location)
                    display_name = subsection.display_name or ""
                    rows.append(
                        [
                            key_str,
                            section_key,
                            subsection_key,
                            "keep",
                            display_name,
                            "",  # industry code — operator fills in
                            "",  # type         — operator fills in
                            "",  # video ID     — operator fills in
                        ]
                    )
                    subsection_count += 1
                section_count += 1

            self.stdout.write(
                f"  {key_str}: {section_count} section(s), "
                f"{subsection_count} subsection(s)"
            )

        if errors:
            for err in errors:
                self.stderr.write(self.style.ERROR(f"  ERROR: {err}"))
            msg = (
                "Errors encountered while loading source courses. "
                "No output file written."
            )
            raise CommandError(msg)

        with Path(output_path).open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(CSV_HEADER)
            writer.writerows(rows)

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCSV template written to '{output_path}' "
                f"({len(rows)} row(s) from {len(source_key_strs)} source course(s)).\n"
                "Next step: fill in 'industry code', 'type', change actions to "
                "'update'/'remove' where needed, then run generate_custom_courses."
            )
        )
