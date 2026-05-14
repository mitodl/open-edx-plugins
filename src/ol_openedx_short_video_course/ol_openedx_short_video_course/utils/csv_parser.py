"""CSV parsing, grouping, and destination key derivation utilities."""

# ruff: noqa: C901

import csv
from dataclasses import dataclass
from pathlib import Path

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import UsageKey
from opaque_keys.edx.locator import CourseLocator

CSV_HEADER = [
    "source_course_key",
    "section",
    "subsection",
    "action",
    "unit display name",
    "industry code",
    "type",
    "video ID",
]

# Normalised column names (lowercase, spaces→underscores) used for dict lookup.
_REQUIRED_COLUMNS = {
    "source_course_key",
    "section",
    "subsection",
    "action",
    "unit_display_name",
    "industry_code",
    "type",
    "video_id",
}

VALID_ACTIONS = {"keep", "remove", "update"}


@dataclass
class CsvRow:
    """A single parsed and validated CSV row."""

    source_course_key_str: str
    section_key_str: str
    subsection_key_str: str
    action: str
    unit_display_name: str
    industry_code: str
    type_code: str
    video_id: str
    line_number: int


def _normalise_key(name: str) -> str:
    """Lower-case and replace spaces with underscores."""
    return name.strip().lower().replace(" ", "_")


def parse_csv(filepath: str) -> list[CsvRow]:
    """
    Parse the CSV file and return a list of CsvRow objects.

    Raises FileNotFoundError if the file does not exist.
    Raises ValueError with a full list of errors if any rows are invalid.
    """
    path = Path(filepath)
    if not path.exists():
        msg = f"CSV file not found: {filepath}"
        raise FileNotFoundError(msg)

    rows: list[CsvRow] = []
    errors: list[str] = []

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)

        if reader.fieldnames is None:
            msg = "CSV file is empty or has no header row."
            raise ValueError(msg)

        normalised_fields = {_normalise_key(f) for f in reader.fieldnames}
        missing = _REQUIRED_COLUMNS - normalised_fields
        if missing:
            msg = f"CSV is missing required columns: {', '.join(sorted(missing))}"
            raise ValueError(msg)

        for line_num, raw_row in enumerate(reader, start=2):
            row = {_normalise_key(k): (v or "").strip() for k, v in raw_row.items()}

            action = row.get("action", "").lower()
            if action not in VALID_ACTIONS:
                errors.append(
                    f"Line {line_num}: invalid action '{row.get('action', '')}'. "
                    f"Must be one of: {', '.join(sorted(VALID_ACTIONS))}"
                )
                continue

            video_id = row.get("video_id", "")
            industry_code = row.get("industry_code", "")
            type_code = row.get("type", "")

            if not industry_code:
                errors.append(f"Line {line_num}: 'industry code' must not be empty")
            if not type_code:
                errors.append(f"Line {line_num}: 'type' must not be empty")

            if action == "update" and not video_id:
                errors.append(
                    f"Line {line_num}: 'video ID' is required when action is 'update'"
                )
            if action != "update" and video_id:
                errors.append(
                    f"Line {line_num}: 'video ID' must be empty for action '{action}'"
                )

            rows.append(
                CsvRow(
                    source_course_key_str=row.get("source_course_key", ""),
                    section_key_str=row.get("section", ""),
                    subsection_key_str=row.get("subsection", ""),
                    action=action,
                    unit_display_name=row.get("unit_display_name", ""),
                    industry_code=industry_code,
                    type_code=type_code,
                    video_id=video_id,
                    line_number=line_num,
                )
            )

    if errors:
        raise ValueError("CSV structural errors:\n" + "\n".join(errors))

    return rows


def group_rows(
    rows: list[CsvRow],
) -> dict[tuple[str, str, str], list[CsvRow]]:
    """
    Group rows by (source_course_key_str, type_code, industry_code).

    Each group defines one destination course.
    """
    groups: dict[tuple[str, str, str], list[CsvRow]] = {}
    for row in rows:
        key = (row.source_course_key_str, row.type_code, row.industry_code)
        groups.setdefault(key, []).append(row)
    return groups


def derive_dest_course_key(
    source_key: CourseLocator, type_code: str, industry_code: str
) -> CourseLocator:
    """
    Build the destination course key from a source CourseLocator.

    Pattern: course-v1:ORG+COURSE_NUM.TYPE.INDUSTRY+RUN
    Example: course-v1:UAI_SOURCE+UAI.2+2T2025 → course-v1:UAI_SOURCE+UAI.2.S.HC+2T2025
    """
    return CourseLocator(
        org=source_key.org,
        course=f"{source_key.course}.{type_code}.{industry_code}",
        run=source_key.run,
    )


def extract_block_id(usage_key_str: str) -> str | None:
    """Return the block_id component of a usage key string, or None if invalid."""
    try:
        return UsageKey.from_string(usage_key_str).block_id
    except InvalidKeyError:
        return None
