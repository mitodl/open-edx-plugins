"""
Copy translations from an already translated course into BlockTranslation rows.

``translate_course`` imports the translated course with ``map_into_course``,
which keeps every block's type and id, so the translated counterpart of a
source block is the block with the same id in the target course.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_course_translations.blocks import (
    GRADER_LABELS_FIELD,
    TRANSLATABLE_BLOCK_FIELDS,
    grader_labels_source,
    grader_labels_value,
    restore_grader_labels,
    restore_kept_parts,
    serialize,
    source_hash,
)
from ol_openedx_course_translations.models import BlockTranslation


def edit_status(source, target):
    """Return STALE when the source was edited after its translated counterpart."""
    source_edited = getattr(source, "edited_on", None)
    target_edited = getattr(target, "edited_on", None)
    if source_edited and target_edited and source_edited > target_edited:
        return BlockTranslation.Status.STALE
    return BlockTranslation.Status.AUTO


def build_rows(source_blocks, get_target_block, language):
    """
    Return unsaved rows for every field whose target value differs from source.

    A source block edited after its counterpart in the target was last changed
    (when ``translate_course`` imported it) may have changed since it was
    translated, so its rows are stored as stale for a person to check.
    Answers, grading code, ids and keys are copied back from the source, and a
    field is skipped when the two values cannot be matched up.
    """
    rows = []
    for block in source_blocks:
        location = block.location
        target = get_target_block(location.block_type, location.block_id)
        if target is None:
            continue
        status = edit_status(block, target)
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


def _subsection_mismatch(subsections, type_mapping):
    """Return why a source subsection's type does not map to its counterpart's."""
    for source, target in subsections:
        block_id = source.location.block_id
        if target is None:
            return f"subsection {block_id} is missing from the target"
        source_format = getattr(source, "format", None)
        if source_format and getattr(target, "format", None) != type_mapping.get(
            source_format
        ):
            return f"subsection {block_id} has another type"
    return None


def grader_labels_backfill_row(source_course, target_course, subsections, language):
    """
    Return ``(row, reason)``: the grading type names row, or None and the reason.

    The two courses name their grading types in different languages, so they are
    paired by position. The pairing is only trusted when both courses have the
    same number of types with the same weights, and every source subsection's
    type maps to its counterpart's type (``subsections`` lists source and target
    subsection pairs).
    """
    source_pairs = grader_labels_source(source_course)
    target_pairs = grader_labels_source(target_course)
    if not source_pairs:
        return None, "the source course has no grading types"

    def weights(course):
        return [grader.get("weight") for grader in course.raw_grader or []]

    if weights(source_course) != weights(target_course):
        return None, "the grading types differ in number or weight"
    type_mapping = {
        source[0]: target[0]
        for source, target in zip(source_pairs, target_pairs, strict=True)
    }
    mismatch = _subsection_mismatch(subsections, type_mapping)
    if mismatch:
        return None, mismatch
    row = grader_labels_translation(source_course, source_pairs, target_pairs, language)
    if row is None:
        return None, "the grading types are not translated or not usable"
    row.status = edit_status(source_course, target_course)
    return row, None


def grader_labels_translation(course, source_pairs, translated_pairs, language):
    """Return an unsaved grading type names row, pairing lists by position, or None."""
    labels = restore_grader_labels(
        source_pairs, serialize(grader_labels_value(source_pairs, translated_pairs))
    )
    if labels is None or translated_pairs == source_pairs:
        return None
    return BlockTranslation(
        course_key=course.location.course_key,
        usage_key=course.location,
        field=GRADER_LABELS_FIELD,
        language=language,
        source_hash=source_hash(source_pairs),
        translated_value=serialize(labels),
        status=BlockTranslation.Status.AUTO,
    )


def save_rows(rows):
    """Upsert rows, leaving reviewed rows untouched. Return the number written."""
    if not rows:
        return 0
    with transaction.atomic():
        return _save_unreviewed_rows(rows)


def _save_unreviewed_rows(rows):
    # The existing rows stay locked until the upsert commits, so a review saved
    # meanwhile waits and is not overwritten.
    existing = (
        BlockTranslation.objects.select_for_update()
        .filter(
            usage_key__in={row.usage_key for row in rows},
            language__in={row.language for row in rows},
        )
        .values_list("usage_key", "field", "language", "status")
    )
    reviewed = {
        (usage_key, field, language)
        for usage_key, field, language, status in existing
        if status == BlockTranslation.Status.REVIEWED
    }
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
        batch_size=500,
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

        source_blocks = [
            block
            for block_type in TRANSLATABLE_BLOCK_FIELDS
            for block in store.get_items(
                source_key, qualifiers={"category": block_type}, revision=published
            )
        ]
        rows = build_rows(source_blocks, get_target_block, language)
        source_course = store.get_course(source_key)
        grader_row, reason = grader_labels_backfill_row(
            source_course,
            store.get_course(target_key),
            [
                (block, get_target_block("sequential", block.location.block_id))
                for block in source_blocks
                if block.location.block_type == "sequential"
            ],
            language,
        )
        if grader_row is None:
            self.stdout.write(f"Grading type names not copied: {reason}.")
        else:
            rows.append(grader_row)
        written = save_rows(rows)
        stale = sum(row.status == BlockTranslation.Status.STALE for row in rows)
        self.stdout.write(
            f"Stored {written} translations for {len(source_blocks)} blocks "
            f"({stale} marked stale)."
        )
