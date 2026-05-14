"""
Course creation utilities for the short-video course plugin.

Builds a new course from scratch using the Open edX modulestore API.
The hierarchy created is:

  Course
    └── Section  (chapter)
          └── Subsection  (sequential)
                └── Unit  (vertical)
                      └── Video block  (video)
"""

import logging
import re
from collections import OrderedDict
from dataclasses import dataclass

from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils.csv_parser import CsvRow

log = logging.getLogger(__name__)


@dataclass
class CreationStats:
    """Counts of structural items created for one course."""

    sections: int = 0
    subsections: int = 0
    units: int = 0


def _slug(text: str) -> str:
    """
    Convert *text* to a lowercase alphanumeric slug suitable for block IDs.

    Non-alphanumeric characters are replaced with underscores, consecutive
    underscores are collapsed, and leading/trailing underscores are stripped.
    """
    return re.sub(r"_+", "_", re.sub(r"[^a-z0-9]+", "_", text.lower())).strip("_")


def create_course(
    course_key: CourseKey,
    course_name: str,
    user_id: int,
) -> None:
    """
    Create a blank course in the modulestore.

    Raises:
        ValueError: if a course with *course_key* already exists.
    """
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415

    store = modulestore()

    if store.get_course(course_key) is not None:
        msg = f"Course already exists: '{course_key}'."
        raise ValueError(msg)

    fields = {"display_name": course_name}
    store.create_course(
        org=course_key.org,
        course=course_key.course,
        run=course_key.run,
        user_id=user_id,
        fields=fields,
    )
    log.info("Created course %s ('%s')", course_key, course_name)


def build_course_structure(
    course_key: CourseKey,
    rows: list[CsvRow],
    user_id: int,
) -> CreationStats:
    """
    Create the full section/subsection/unit/video hierarchy for one course.

    *rows* are the CsvRow objects for this course, in CSV order.
    The function preserves insertion order so that sections and subsections
    appear in the CSV-specified order.

    Returns a CreationStats with counts of created items.
    """
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415

    store = modulestore()
    stats = CreationStats()

    # Build an ordered mapping:
    #   section_name → OrderedDict(subsection_name → [CsvRow, ...])
    sections: dict[str, dict[str, list[CsvRow]]] = OrderedDict()
    for row in rows:
        if row.section_name not in sections:
            sections[row.section_name] = OrderedDict()
        if row.subsection_name not in sections[row.section_name]:
            sections[row.section_name][row.subsection_name] = []
        sections[row.section_name][row.subsection_name].append(row)

    course_block = store.get_course(course_key, depth=0)

    with store.bulk_operations(course_key):
        for section_name, subsections in sections.items():
            section_id = f"section_{_slug(section_name)}"
            section_block = store.create_child(
                user_id,
                course_block.location,
                "chapter",
                block_id=section_id,
                fields={"display_name": section_name},
            )
            stats.sections += 1
            log.debug("Created section '%s' (%s)", section_name, section_id)

            for subsection_name, unit_rows in subsections.items():
                subsection_id = f"subsection_{_slug(subsection_name)}"
                subsection_block = store.create_child(
                    user_id,
                    section_block.location,
                    "sequential",
                    block_id=subsection_id,
                    fields={"display_name": subsection_name},
                )
                stats.subsections += 1
                log.debug(
                    "Created subsection '%s' (%s)", subsection_name, subsection_id
                )

                for row in unit_rows:
                    unit_id = f"unit_{_slug(row.vertical_name)}"
                    unit_block = store.create_child(
                        user_id,
                        subsection_block.location,
                        "vertical",
                        block_id=unit_id,
                        fields={"display_name": row.vertical_name},
                    )
                    stats.units += 1
                    log.debug("Created unit '%s' (%s)", row.vertical_name, unit_id)

                    video_id = f"video_{_slug(row.vertical_name)}"
                    video_fields: dict[str, object] = {
                        "display_name": row.vertical_name,
                    }
                    if row.edx_video_id:
                        video_fields["edx_video_id"] = row.edx_video_id

                    store.create_child(
                        user_id,
                        unit_block.location,
                        "video",
                        block_id=video_id,
                        fields=video_fields,
                    )
                    log.debug(
                        "Created video block '%s' (edx_video_id=%s)",
                        video_id,
                        row.edx_video_id or "(none)",
                    )

    log.info(
        "Built structure for %s: %d section(s), %d subsection(s), %d unit(s)",
        course_key,
        stats.sections,
        stats.subsections,
        stats.units,
    )
    return stats
