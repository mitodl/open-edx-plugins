"""Course transformation engine: applies CSV actions to a destination course."""

# ruff: noqa: C901

import logging
from dataclasses import dataclass

from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils.csv_parser import CsvRow, extract_block_id

log = logging.getLogger(__name__)


@dataclass
class TransformResult:
    """Counts of subsections affected by each action."""

    kept: int = 0
    removed: int = 0
    updated: int = 0
    empty_sections_removed: int = 0


def apply_group_actions(
    dest_key: CourseKey,
    group_rows: list[CsvRow],
    user_id: int,
) -> TransformResult:
    """
    Apply CSV actions to the destination course in a single pass.

    Order of operations:
    1. Remove subsections marked ``remove``.
    2. After all removals, delete sections whose children list is now empty.
    3. Replace units in subsections marked ``update`` with a single video unit.
    4. Leave subsections marked ``keep`` untouched (they were deep-cloned).

    All operations on a single destination course are wrapped in
    ``store.bulk_operations`` for performance.
    """
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415

    result = TransformResult()
    store = modulestore()

    # Build lookup: subsection_block_id → CsvRow for O(1) access.
    row_lookup: dict[str, CsvRow] = {}
    for row in group_rows:
        sub_id = extract_block_id(row.subsection_key_str)
        if sub_id:
            row_lookup[sub_id] = row

    with store.bulk_operations(dest_key):
        course = store.get_course(dest_key, depth=4)
        if course is None:
            msg = f"Destination course not found after clone: '{dest_key}'"
            raise ValueError(msg)

        sections_to_remove: list = []

        for section in course.get_children():
            section_has_remaining = False

            for subsection in section.get_children():
                sub_block_id = subsection.location.block_id
                row = row_lookup.get(sub_block_id)

                if row is None:
                    # Unmapped subsection — post-validation should not happen;
                    # treat as keep to avoid accidental data loss.
                    log.warning(
                        "Subsection '%s' not in CSV row_lookup; treating as keep.",
                        sub_block_id,
                    )
                    section_has_remaining = True
                    result.kept += 1
                    continue

                if row.action == "keep":
                    section_has_remaining = True
                    result.kept += 1

                elif row.action == "remove":
                    log.debug("Removing subsection %s", subsection.location)
                    store.delete_item(subsection.location, user_id)
                    result.removed += 1

                elif row.action == "update":
                    _replace_with_video_unit(store, subsection, row, user_id)
                    section_has_remaining = True
                    result.updated += 1

            if not section_has_remaining:
                sections_to_remove.append(section.location)

        for section_loc in sections_to_remove:
            log.debug("Removing now-empty section %s", section_loc)
            store.delete_item(section_loc, user_id)
            result.empty_sections_removed += 1

    return result


def _replace_with_video_unit(store, subsection, row: CsvRow, user_id: int) -> None:
    """
    Clear all existing units from *subsection* and add one video unit.

    Uses stable block IDs derived from the subsection's block_id so that
    repeated runs produce the same IDs (idempotent at the ID level).
    """
    subsection_loc = subsection.location
    sub_block_id = subsection_loc.block_id

    # Remove every existing vertical (unit) in this subsection.
    for unit in subsection.get_children():
        store.delete_item(unit.location, user_id)

    display_name = row.unit_display_name or subsection.display_name or "Video"

    # Stable, predictable block IDs.
    unit_block_id = f"svg_{sub_block_id}_unit"
    video_block_id = f"svg_{sub_block_id}_video"

    log.debug(
        "Creating video unit '%s' (block_id=%s) in subsection %s",
        display_name,
        unit_block_id,
        subsection_loc,
    )

    new_unit = store.create_child(
        user_id,
        subsection_loc,
        "vertical",
        block_id=unit_block_id,
        fields={"display_name": display_name},
    )

    store.create_child(
        user_id,
        new_unit.location,
        "video",
        block_id=video_block_id,
        fields={
            "display_name": display_name,
            "edx_video_id": row.video_id,
        },
    )
