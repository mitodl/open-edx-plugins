"""
Utilities for the short-video course plugin.

Covers two concerns:

1. CSV parsing and grouping — reading the input mapping file into CsvRow
   objects and grouping them by course key.

2. Course creation — building a new course and its full section/subsection/
   unit/video hierarchy in the Open edX modulestore.
"""

import csv
import logging
import re
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# CSV constants
# ---------------------------------------------------------------------------

CSV_HEADER = [
    "course_name",
    "course_key",
    "section_name",
    "subsection_name",
    "vertical_name",
    "edx_video_id",
]

_REQUIRED_COLUMNS = {
    "course_name",
    "course_key",
    "section_name",
    "subsection_name",
    "vertical_name",
    "edx_video_id",
}


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CsvRow:
    """A single parsed and validated CSV row."""

    course_name: str
    course_key_str: str
    section_name: str
    subsection_name: str
    vertical_name: str
    edx_video_id: str
    line_number: int


@dataclass
class CreationStats:
    """Counts of structural items created for one course."""

    sections: int = 0
    subsections: int = 0
    units: int = 0


# CourseGroups maps course_key_str → ordered list of CsvRow for that course
CourseGroups = dict[str, list[CsvRow]]


# ---------------------------------------------------------------------------
# CSV parsing
# ---------------------------------------------------------------------------


def _normalise_key(name: str) -> str:
    """Lower-case and replace spaces with underscores."""
    return name.strip().lower().replace(" ", "_")


def parse_csv(filepath: str) -> list[CsvRow]:
    """
    Parse a short-video course CSV file and return a list of CsvRow objects.

    Raises:
        FileNotFoundError: if the file does not exist.
        ValueError: if required columns are missing or row data is invalid.
    """
    path = Path(filepath)
    if not path.exists():
        msg = f"CSV file not found: '{filepath}'"
        raise FileNotFoundError(msg)

    rows: list[CsvRow] = []

    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            msg = "CSV file is empty or has no header row."
            raise ValueError(msg)

        normalised_fields = {_normalise_key(f) for f in reader.fieldnames}
        missing = _REQUIRED_COLUMNS - normalised_fields
        if missing:
            msg = f"CSV is missing required columns: {', '.join(sorted(missing))}"
            raise ValueError(msg)

        for line_number, raw_row in enumerate(reader, start=2):
            normalised = {_normalise_key(k): v.strip() for k, v in raw_row.items()}

            for col in (
                "course_name",
                "course_key",
                "section_name",
                "subsection_name",
                "vertical_name",
            ):
                if not normalised.get(col):
                    msg = f"Line {line_number}: '{col}' must not be empty."
                    raise ValueError(msg)

            rows.append(
                CsvRow(
                    course_name=normalised["course_name"],
                    course_key_str=normalised["course_key"],
                    section_name=normalised["section_name"],
                    subsection_name=normalised["subsection_name"],
                    vertical_name=normalised["vertical_name"],
                    edx_video_id=normalised.get("edx_video_id", ""),
                    line_number=line_number,
                )
            )

    if not rows:
        msg = "CSV file contains no data rows."
        raise ValueError(msg)

    return rows


def group_rows(rows: list[CsvRow]) -> CourseGroups:
    """
    Group CSV rows by course_key, preserving insertion order.

    Returns an OrderedDict mapping course_key_str → [CsvRow, ...].
    """
    groups: CourseGroups = OrderedDict()
    for row in rows:
        groups.setdefault(row.course_key_str, []).append(row)
    return groups


# ---------------------------------------------------------------------------
# Course creation
# ---------------------------------------------------------------------------


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

    store.create_course(
        org=course_key.org,
        course=course_key.course,
        run=course_key.run,
        user_id=user_id,
        fields={"display_name": course_name},
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
    Insertion order is preserved so sections and subsections appear in the
    same order as the CSV rows.

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
