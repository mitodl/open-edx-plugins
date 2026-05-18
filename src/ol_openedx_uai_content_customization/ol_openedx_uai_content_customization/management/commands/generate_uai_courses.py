"""
Management command: generate_uai_courses

Reads two CSV files and uses Open edX modulestore APIs to build industry- and
length-specific variants of UAI courses by cloning a base course:

  - Customized video CSV  (produced by the video-generation workflow)
  - Open edX video asset CSV (exported from Studio / OVS)

For each unique (course_key, industry, duration) combination the command:
    1. Clones the source course (identified by the ``course_key`` CSV column)
     into a new UAI-specific course key, preserving all course settings.
  2. Deletes every existing section from the clone.
  3. Rebuilds the content tree from the CSV data:

        Course  (cloned, settings inherited)
        └── Lectures  (chapter)
            └── <Video Title>  (sequential)
                └── <Video Title>  (vertical)
                    └── <Video Title>  (video block)

Usage:
    python manage.py generate_uai_courses \\
        --customized-csv /path/to/customized.csv \\
        --video-assets-csv /path/to/video_assets.csv \\
        [--username studio_worker] \\
        [--dry-run]

Note: this command writes to the MongoDB-backed modulestore.  Django's
transaction.atomic() does NOT cover MongoDB, so course creation is not
atomic.  If a run fails partway through, already-created courses will remain
and subsequent runs will raise DuplicateCourseError for them (skipped with a
warning).
"""

import logging

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from xmodule.modulestore.django import modulestore
from xmodule.modulestore.exceptions import DuplicateCourseError

from ol_openedx_uai_content_customization.constants import (
    BLOCK_TYPE_CHAPTER,
    BLOCK_TYPE_SEQUENTIAL,
    BLOCK_TYPE_VERTICAL,
    BLOCK_TYPE_VIDEO,
    CSV_COL_MODULE_NAME,
    CSV_COL_VIDEO_FILE,
    CSV_COL_VIDEO_TITLE,
    LECTURES_SECTION_DISPLAY_NAME,
    REQUIRED_ASSET_CSV_COLS,
    REQUIRED_CUSTOMIZED_CSV_COLS,
)
from ol_openedx_uai_content_customization.csv_utils import (
    build_new_course_key,
    build_video_id_map,
    group_videos_by_course,
    parse_csv,
    validate_csv_columns,
)
from ol_openedx_uai_content_customization.modulestore_utils import (
    clone_course_in_modulestore,
    create_content_block,
    delete_course_sections,
    save_video_block_with_edx_video_id,
)

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """Generate industry/length-specific UAI courses using Open edX modulestore APIs."""

    help = (
        "Generate industry- and length-specific UAI courses by reading two CSV files "
        "and creating courses in the CMS modulestore."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--customized-csv",
            required=True,
            help="Path to the customized video metadata CSV file.",
        )
        parser.add_argument(
            "--video-assets-csv",
            required=True,
            help="Path to the Open edX video asset CSV file (exported from"
            " Studio/OVS).",
        )
        parser.add_argument(
            "--username",
            default="studio_worker",
            help="Username of the platform user under whose authority courses are"
            " created (default: studio_worker).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Log what would be created without writing to the modulestore.",
        )

    def handle(self, *args, **options):  # noqa: ARG002, PLR0915
        customized_csv = options["customized_csv"]
        video_assets_csv = options["video_assets_csv"]
        username = options["username"]
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN — no changes will be written.")
            )

        User = get_user_model()
        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            msg = f"No user found with username {username!r}."
            raise CommandError(msg)  # noqa: B904
        customized_rows, customized_fieldnames = parse_csv(customized_csv)
        video_asset_rows, video_asset_fieldnames = parse_csv(video_assets_csv)

        try:
            validate_csv_columns(
                customized_fieldnames,
                REQUIRED_CUSTOMIZED_CSV_COLS,
                "customized video CSV",
            )
            validate_csv_columns(
                video_asset_fieldnames,
                REQUIRED_ASSET_CSV_COLS,
                "video asset CSV",
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        video_id_map = build_video_id_map(video_asset_rows)

        self.stdout.write(
            f"Loaded {len(customized_rows)} customized video rows "
            f"and {len(video_asset_rows)} video asset rows."
        )

        course_groups = group_videos_by_course(customized_rows)
        self.stdout.write(f"Found {len(course_groups)} course variant(s) to create.")

        self._validate_source_course_keys(course_groups)

        created, skipped = 0, 0

        for (orig_key, industry, duration), videos in course_groups.items():
            source_key = CourseKey.from_string(orig_key)  # safe — already validated
            try:
                new_key = build_new_course_key(orig_key, industry, duration)
            except ValueError as exc:
                self.stdout.write(
                    self.style.WARNING(
                        f"  Skipping [{industry}, {duration}] from {orig_key}: {exc}"
                    )
                )
                skipped += 1
                continue

            display_name = self._build_display_name(videos)

            self.stdout.write(f"\n-> {orig_key} [{industry}, {duration}] -> {new_key}")
            self.stdout.write(f"  Display name : {display_name}")
            self.stdout.write(f"  Videos       : {len(videos)}")

            if dry_run:
                for video in videos:
                    vid_file = video[CSV_COL_VIDEO_FILE]
                    vid_title = video[CSV_COL_VIDEO_TITLE]
                    mapped_id = video_id_map.get(vid_file, "<NOT FOUND>")
                    self.stdout.write(f"    - {vid_title} ({vid_file} -> {mapped_id})")
                skipped += 1
                continue

            try:
                self._create_course(
                    source_key,
                    new_key,
                    display_name,
                    videos,
                    video_id_map,
                    user,
                )
                created += 1
            except DuplicateCourseError:
                self.stdout.write(
                    self.style.WARNING(f"  Course {new_key} already exists — skipping.")
                )
                skipped += 1
            except Exception as exc:
                log.exception("Failed to create course %s", new_key)
                msg = f"Failed to create course {new_key}: {exc}"
                raise CommandError(msg) from exc

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. Created: {created}  Skipped: {skipped}")
        )

    def _build_display_name(self, videos):
        """
        Return the module name from the first video row as the course display name.

        Falls back to "UAI Course" when no module name is available.
        """
        module_name = videos[0].get(CSV_COL_MODULE_NAME, "").strip() if videos else ""
        return module_name or "UAI Course"

    def _validate_source_course_keys(self, course_groups):
        """
        Raise CommandError if any source course key in the CSV is invalid or absent.

        Collects all failures before raising so the operator sees every problem
        in a single run rather than one at a time.

        Args:
            course_groups: dict keyed by (orig_key, industry, duration).
        """
        store = modulestore()
        unique_keys = sorted({orig_key for orig_key, _, _ in course_groups})
        missing = []
        for key_str in unique_keys:
            try:
                parsed = CourseKey.from_string(key_str)
            except InvalidKeyError:
                missing.append(f"{key_str!r} (invalid course key format)")
                continue
            if not store.has_course(parsed):
                missing.append(key_str)
        if missing:
            missing_list = "\n".join(f"  - {k}" for k in missing)
            msg = f"Source course(s) not found in the modulestore:\n{missing_list}"
            raise CommandError(msg)

    def _create_course(  # noqa: PLR0913
        self, source_key, course_key_str, display_name, videos, video_id_map, user
    ):
        """
        Clone the source course, strip its sections, then populate with UAI content.

        The clone inherits all course settings (grading, certificates, pacing,
        advanced settings) from the source.  After cloning, every existing
        section is removed and a fresh "Lectures" section is built from the CSV
        data with one subsection → unit → video block per video row.

        All modulestore writes are wrapped in bulk_operations for performance.
        """
        parsed_key = CourseKey.from_string(course_key_str)
        user_id = user.id
        store = modulestore()
        with store.bulk_operations(parsed_key):
            course = clone_course_in_modulestore(
                source_key,
                parsed_key.org,
                parsed_key.course,
                parsed_key.run,
                display_name,
                user_id,
            )
            delete_course_sections(course, user_id)
            section = create_content_block(
                course,
                BLOCK_TYPE_CHAPTER,
                LECTURES_SECTION_DISPLAY_NAME,
                user_id,
            )

            unmapped = []

            for video in videos:
                title = video[CSV_COL_VIDEO_TITLE]
                vid_file = video[CSV_COL_VIDEO_FILE]
                edx_video_id = video_id_map.get(vid_file)

                if not edx_video_id:
                    log.warning(
                        "No Open edX video ID found for file '%s'"
                        " (title: '%s') - skipping.",
                        vid_file,
                        title,
                    )
                    unmapped.append(vid_file)
                    continue

                subsection = create_content_block(
                    section,
                    BLOCK_TYPE_SEQUENTIAL,
                    title,
                    user_id,
                )
                unit = create_content_block(
                    subsection,
                    BLOCK_TYPE_VERTICAL,
                    title,
                    user_id,
                )
                video_block = create_content_block(
                    unit,
                    BLOCK_TYPE_VIDEO,
                    title,
                    user_id,
                )
                save_video_block_with_edx_video_id(video_block, user, edx_video_id)

        store.publish(course.location, user_id)
        if unmapped:
            self.stdout.write(
                self.style.WARNING(
                    f"  Warning: {len(unmapped)} video file(s) had no"
                    f" matching Open edX video ID: " + ", ".join(unmapped)
                )
            )
