"""
Copy an imported course's video thumbnails from the source instance's storage.

Studio export/import carries each thumbnail's storage key but not the image,
so after importing an xPRO course the thumbnails point at files that only
exist in xPRO's bucket. This command downloads the missing files and saves
them under the same keys. Thumbnails already present are left alone, so it is
safe to run again.

Usage:
    python manage.py cms copy_xpro_video_thumbnails <course_key> \
    [--source-base-url URL] [--dry-run]

Options:
    --source-base-url URL
        Public base URL of the source media storage. Defaults to the
        OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL setting.
    --dry-run
        List what would be copied without downloading or saving anything.

Example:
    python manage.py cms copy_xpro_video_thumbnails "course-v1:xPRO+T1+R1" \
        --source-base-url https://xpro-production-edxapp-storage.s3.amazonaws.com/media/
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_video_thumbnail_copy.thumbnails import copy_course_thumbnails


class Command(BaseCommand):
    """Copy a course's video thumbnails from the source instance's storage."""

    help = __doc__

    def add_arguments(self, parser):
        """Add the course key and options."""
        parser.add_argument("course_key", help="Course key on this instance.")
        parser.add_argument(
            "--source-base-url",
            help="Public base URL of the source media storage.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only list what would be copied.",
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Copy the thumbnails and print a summary."""
        try:
            course_key = CourseKey.from_string(options["course_key"])
        except InvalidKeyError as exc:
            msg = f"Invalid course key: {options['course_key']}"
            raise CommandError(msg) from exc

        source_base_url = options["source_base_url"] or getattr(
            settings, "OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL", None
        )
        if not source_base_url:
            msg = (
                "No source base URL: pass --source-base-url or set "
                "OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL"
            )
            raise CommandError(msg)

        result = copy_course_thumbnails(
            course_key, source_base_url, dry_run=options["dry_run"]
        )

        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(f"{prefix}Copied: {len(result.copied)}")
        self.stdout.write(f"{prefix}Skipped: {len(result.skipped)}")
        self.stdout.write(f"{prefix}Missing: {len(result.missing)}")
        for key in result.missing:
            self.stdout.write(f"  missing: {key}")
