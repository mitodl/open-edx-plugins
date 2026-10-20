"""
Copy translations from an already translated course into BlockTranslation rows.

``translate_course`` imports the translated course with ``map_into_course``,
which keeps every block's type and id, so the translated counterpart of a
source block is the block with the same id in the target course.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_course_translations.api import source_hash
from ol_openedx_course_translations.blocks import (
    TRANSLATABLE_BLOCK_FIELDS,
    restore_kept_parts,
    serialize,
)
from ol_openedx_course_translations.models import BlockTranslation, CourseTranslationLog


def build_rows(source_blocks, get_target_block, language, translated_at):
    """
    Return unsaved rows for every field whose target value differs from source.

    A source block edited after ``translated_at`` may have changed since the
    target was made, so its rows are stored as stale for a person to check.
    Answers, grading code, ids and keys are copied back from the source, and a
    field is skipped when the two values cannot be matched up.
    """
    rows = []
    for block in source_blocks:
        location = block.location
        target = get_target_block(location.block_type, location.block_id)
        if target is None:
            continue
        edited_on = getattr(block, "edited_on", None)
        status = (
            BlockTranslation.Status.STALE
            if translated_at and edited_on and edited_on > translated_at
            else BlockTranslation.Status.AUTO
        )
        for field in TRANSLATABLE_BLOCK_FIELDS[location.block_type]:
            source_value = getattr(block, field, None)
            translated_value = getattr(target, field, None)
            # Compared before restoring: re-serialising XML or JSON changes its
            # text even when nothing was translated.
            if not translated_value or translated_value == source_value:
                continue
            translated_value = restore_kept_parts(
                location.block_type, field, source_value, serialize(translated_value)
            )
            if translated_value is None:
                continue
            rows.append(
                BlockTranslation(
                    course_key=location.course_key,
                    usage_key=location,
                    field=field,
                    language=language,
                    source_hash=source_hash(source_value),
                    translated_value=serialize(translated_value),
                    status=status,
                )
            )
    return rows


def save_rows(rows):
    """Upsert rows, leaving reviewed rows untouched. Return the number written."""
    if not rows:
        return 0
    reviewed = set(
        BlockTranslation.objects.filter(
            usage_key__in={row.usage_key for row in rows},
            language__in={row.language for row in rows},
            status=BlockTranslation.Status.REVIEWED,
        ).values_list("usage_key", "field", "language")
    )
    rows = [
        row for row in rows if (row.usage_key, row.field, row.language) not in reviewed
    ]
    # MySQL upserts on any unique key and rejects naming the conflict target.
    unique_fields = (
        ["usage_key", "field", "language"]
        if connection.features.supports_update_conflicts_with_target
        else None
    )
    BlockTranslation.objects.bulk_create(
        rows,
        update_conflicts=True,
        unique_fields=unique_fields,
        update_fields=["source_hash", "translated_value", "status", "updated_at"],
    )
    return len(rows)


class Command(BaseCommand):
    """Backfill in-place translations from a course made by translate_course."""

    help = __doc__

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument("--source", required=True, help="Source course id")
        parser.add_argument(
            "--target", required=True, help="Translated course id made from it"
        )
        parser.add_argument(
            "--language", required=True, help="Language of the target, e.g. fr"
        )

    def handle(self, *args, **options):  # noqa: ARG002
        """Read both courses' published blocks and store the differences."""
        # xmodule exists only inside edx-platform.
        from xmodule.modulestore import ModuleStoreEnum  # noqa: PLC0415
        from xmodule.modulestore.django import modulestore  # noqa: PLC0415
        from xmodule.modulestore.exceptions import ItemNotFoundError  # noqa: PLC0415

        try:
            source_key = CourseKey.from_string(options["source"])
            target_key = CourseKey.from_string(options["target"])
        except InvalidKeyError as error:
            raise CommandError(str(error)) from error
        language = options["language"].lower().replace("_", "-")
        if language not in dict(settings.LANGUAGES):
            msg = f"--language must be a code from settings.LANGUAGES, got {language}."
            raise CommandError(msg)

        store = modulestore()
        published = ModuleStoreEnum.RevisionOption.published_only
        if not store.has_course(source_key) or not store.has_course(target_key):
            msg = "Both --source and --target must be existing courses."
            raise CommandError(msg)

        def get_target_block(block_type, block_id):
            try:
                return store.get_item(
                    target_key.make_usage_key(block_type, block_id),
                    revision=published,
                )
            except ItemNotFoundError:
                return None

        latest_log = (
            CourseTranslationLog.objects.filter(
                source_course_id=source_key,
                target_course_language__iexact=language,
            )
            .order_by("-created_at")
            .first()
        )
        source_blocks = [
            block
            for block_type in TRANSLATABLE_BLOCK_FIELDS
            for block in store.get_items(
                source_key, qualifiers={"category": block_type}, revision=published
            )
        ]
        rows = build_rows(
            source_blocks,
            get_target_block,
            language,
            latest_log.created_at if latest_log else None,
        )
        written = save_rows(rows)
        stale = sum(row.status == BlockTranslation.Status.STALE for row in rows)
        self.stdout.write(
            f"Stored {written} translations for {len(source_blocks)} blocks "
            f"({stale} marked stale)."
        )
