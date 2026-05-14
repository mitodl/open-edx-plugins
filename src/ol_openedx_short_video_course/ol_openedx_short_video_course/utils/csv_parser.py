"""CSV parsing and grouping utilities for the short-video course creator."""

import csv
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

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


# CourseGroups maps course_key_str → ordered list of CsvRow for that course
CourseGroups = dict[str, list[CsvRow]]


def group_rows(rows: list[CsvRow]) -> CourseGroups:
    """
    Group CSV rows by course_key, preserving insertion order.

    Returns an OrderedDict mapping course_key_str → [CsvRow, ...].
    """
    groups: CourseGroups = OrderedDict()
    for row in rows:
        groups.setdefault(row.course_key_str, []).append(row)
    return groups
