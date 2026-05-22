"""CSV parsing and video-mapping utilities for ol-openedx-uai-content-customization."""

import csv
from collections import defaultdict
from pathlib import Path

from opaque_keys.edx.keys import CourseKey

from ol_openedx_uai_content_customization.constants import (
    CSV_COL_ASSET_NAME,
    CSV_COL_ASSET_VIDEO_ID,
    CSV_COL_COURSE_KEY,
    CSV_COL_DURATION,
    CSV_COL_INDUSTRY,
    DURATION_CODES,
    INDUSTRY_CODES,
)


def parse_csv(path):
    """
    Read a CSV file and return a ``(rows, fieldnames)`` tuple.

    Returns:
        tuple: A 2-tuple ``(rows, fieldnames)`` where *rows* is a list of
        ``dict`` objects (one per data row) and *fieldnames* is the list of
        column header strings as they appear in the file.  Both are empty
        lists when the file contains no header row at all.
    """
    with Path(path).open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    fieldnames = [col.lower() for col in fieldnames]
    rows = [{col.lower(): value for col, value in row.items()} for row in rows]
    return rows, fieldnames


def validate_csv_columns(fieldnames, required_cols, csv_label):
    """
    Raise ValueError if any required column is absent from the CSV headers.

    Args:
        fieldnames: List of column header strings returned by parse_csv().
        required_cols: Iterable of column names that must be present.
        csv_label: Human-readable label used in the error message.

    Raises:
        ValueError: describing which columns are missing.
    """
    actual_cols = {col.lower() for col in fieldnames}
    missing = [col for col in required_cols if col.lower() not in actual_cols]
    if missing:
        msg = f"{csv_label} is missing required columns: {', '.join(missing)}"
        raise ValueError(msg)


def build_video_id_map(video_asset_rows):
    """
    Build a mapping of video file name → Open edX video ID.

    Args:
        video_asset_rows: Rows from the Open edX video asset CSV.

    Returns:
        dict mapping file name (e.g. "v004_h264.mp4") to video UUID string.
    """
    return {
        row[CSV_COL_ASSET_NAME]: row[CSV_COL_ASSET_VIDEO_ID] for row in video_asset_rows
    }


def resolve_duration_code(duration_value):
    """
    Convert a duration cell value into a Short/Full code.

    The CSV must provide explicit values: "short" or "long"
    (case-insensitive).

    Args:
        duration_value: Raw string from the Duration column.

    Returns:
        "S" or "F"

    Raises:
        ValueError: if the value is not one of "short" or "long".
    """
    value = str(duration_value).strip().lower()

    if value in DURATION_CODES:
        return DURATION_CODES[value]

    msg = (
        "Unrecognised duration value "
        f"{duration_value!r}. Expected one of: {', '.join(DURATION_CODES)}"
    )
    raise ValueError(msg)


def build_new_course_key(original_key, industry, duration_value):
    """
    Generate a new course key for the given industry and duration.

    Format:  course-v1:ORG+NUMBER.<DURATION>[.<INDUSTRY>]+RUN

    For "Original industry" no industry code is appended, so the format is:
        course-v1:ORG+NUMBER.<DURATION>+RUN

    Args:
        original_key: e.g. "course-v1:UAI_SOURCE+UAI.2+1T2026"
        industry: Industry name string as it appears in the CSV.
        duration_value: Raw Duration column value.

    Returns:
        New course key string.
    """
    parsed = CourseKey.from_string(original_key)
    org = parsed.org
    number = parsed.course
    run = parsed.run

    dur_code = resolve_duration_code(duration_value)

    if industry not in INDUSTRY_CODES:
        known = ", ".join(INDUSTRY_CODES)
        msg = f"Unrecognised industry {industry!r}. Must be one of: {known}"
        raise ValueError(msg)
    ind_code = INDUSTRY_CODES[industry]

    if ind_code:
        new_number = f"{number}.{dur_code}.{ind_code}"
    else:
        new_number = f"{number}.{dur_code}"

    return f"course-v1:{org}+{new_number}+{run}"


def group_videos_by_course(customized_rows):
    """
    Group video rows by (original_course_key, industry, duration).

    Returns:
        dict mapping (course_key, industry, duration) → list of row dicts.
    """
    groups = defaultdict(list)
    for row in customized_rows:
        key = (
            row[CSV_COL_COURSE_KEY],
            row[CSV_COL_INDUSTRY],
            row[CSV_COL_DURATION],
        )
        groups[key].append(row)
    return groups
