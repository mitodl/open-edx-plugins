"""Tests for ol_openedx_uai_content_customization csv_utils."""

import pytest
from ol_openedx_uai_content_customization.csv_utils import (
    build_new_course_key,
    build_video_id_map,
    group_videos_by_course,
    parse_csv,
    resolve_duration_code,
    validate_csv_columns,
)

# ---------------------------------------------------------------------------
# parse_csv
# ---------------------------------------------------------------------------


def test_parse_csv_returns_list_of_dicts(tmp_path):
    """Each row in the CSV is returned as a dict keyed by column header."""
    csv_text = "Name,Video ID\nv004_h264.mp4,abc-123\nv005_h264.mp4,def-456\n"
    csv_file = tmp_path / "assets.csv"
    csv_file.write_text(csv_text)

    rows, fieldnames = parse_csv(str(csv_file))

    assert len(rows) == 2  # noqa: PLR2004
    assert rows[0]["Name"] == "v004_h264.mp4"
    assert rows[0]["Video ID"] == "abc-123"
    assert fieldnames == ["Name", "Video ID"]


def test_parse_csv_empty_file(tmp_path):
    """A CSV with only a header row returns an empty row list but keeps the headers."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("Name,Video ID\n")

    rows, fieldnames = parse_csv(str(csv_file))

    assert rows == []
    assert fieldnames == ["Name", "Video ID"]


# ---------------------------------------------------------------------------
# validate_csv_columns
# ---------------------------------------------------------------------------


def test_validate_csv_columns_passes_when_all_present():
    """No exception is raised when all required columns are present."""
    validate_csv_columns(
        ["Name", "Video ID"], ["Name", "Video ID"], "test CSV"
    )  # no exception


def test_validate_csv_columns_raises_on_missing_column():
    """ValueError is raised listing every missing column."""
    with pytest.raises(ValueError, match="missing required columns"):
        validate_csv_columns(["Name"], ["Name", "Video ID"], "test CSV")


def test_validate_csv_columns_raises_for_header_only_csv():
    """A header-only CSV (no data rows) still validates columns when some are absent.

    Previously, an empty ``rows`` list caused the validation to be skipped
    entirely.  Now ``fieldnames`` is always inspected regardless of whether
    there are data rows.
    """
    # Simulate a CSV that has a header row but no data rows, where the header
    # is missing a required column.  In the old code this would silently pass.
    with pytest.raises(ValueError, match="missing required columns"):
        validate_csv_columns(["Name"], ["Name", "Video ID"], "test CSV")


def test_validate_csv_columns_passes_for_header_only_csv_with_all_cols():
    """A header-only CSV with all required columns present should not raise."""
    validate_csv_columns(
        ["Name", "Video ID"], ["Name", "Video ID"], "test CSV"
    )  # no exception expected


def test_validate_csv_columns_raises_for_completely_empty_csv():
    """A completely empty file (no header) raises because all columns are missing."""
    with pytest.raises(ValueError, match="missing required columns"):
        validate_csv_columns([], ["Name", "Video ID"], "test CSV")


# ---------------------------------------------------------------------------
# build_video_id_map
# ---------------------------------------------------------------------------


def test_build_video_id_map():
    """Returns a dict mapping each video file name to its Open edX video UUID."""
    rows = [
        {"Name": "v004_h264.mp4", "Video ID": "abc-123"},
        {"Name": "v005_h264.mp4", "Video ID": "def-456"},
    ]
    mapping = build_video_id_map(rows)

    assert mapping == {
        "v004_h264.mp4": "abc-123",
        "v005_h264.mp4": "def-456",
    }


def test_build_video_id_map_empty():
    """An empty asset row list produces an empty mapping."""
    assert build_video_id_map([]) == {}


# ---------------------------------------------------------------------------
# resolve_duration_code
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("duration_value", "expected"),
    [
        ("10", "S"),  # numeric short
        ("30", "S"),  # exactly at threshold
        ("31", "F"),  # just above threshold
        ("long", "F"),  # literal "long"
        ("Long", "F"),  # case-insensitive "Long"
        ("short", "S"),  # literal "short"
        ("Short", "S"),  # case-insensitive "Short"
    ],
)
def test_resolve_duration_code(duration_value, expected):
    """Parametrised check that duration strings map to the correct S/F code."""
    assert resolve_duration_code(duration_value) == expected


def test_resolve_duration_code_unknown_defaults_to_short():
    """An unrecognised duration string falls back to the Short (S) code."""
    assert resolve_duration_code("unknown_value") == "S"


# ---------------------------------------------------------------------------
# build_new_course_key
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("orig_key", "industry", "duration", "expected"),
    [
        # Healthcare, Short
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Healthcare",
            "10",
            "course-v1:UAI_SOURCE+UAI.2.S.HC+1T2026",
        ),
        # Healthcare, Full
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Healthcare",
            "long",
            "course-v1:UAI_SOURCE+UAI.2.F.HC+1T2026",
        ),
        # Finance, Short
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Finance",
            "10",
            "course-v1:UAI_SOURCE+UAI.2.S.F+1T2026",
        ),
        # Energy, Full
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Energy",
            "long",
            "course-v1:UAI_SOURCE+UAI.3.F.E+1T2026",
        ),
        # Original industry, Short — no industry code
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Original industry",
            "10",
            "course-v1:UAI_SOURCE+UAI.3.S+1T2026",
        ),
        # Original industry, Full — no industry code
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Original industry",
            "long",
            "course-v1:UAI_SOURCE+UAI.3.F+1T2026",
        ),
    ],
)
def test_build_new_course_key(orig_key, industry, duration, expected):
    """Parametrised check that course keys are generated with correct org/number/run."""
    assert build_new_course_key(orig_key, industry, duration) == expected


def test_build_new_course_key_unknown_industry_raises():
    """An unrecognised industry name raises ValueError instead of silently
    continuing.
    """
    with pytest.raises(ValueError, match="Unrecognised industry"):
        build_new_course_key(
            "course-v1:UAI_SOURCE+UAI.2+1T2026", "Unknown Industry", "10"
        )


# ---------------------------------------------------------------------------
# group_videos_by_course
# ---------------------------------------------------------------------------


def _make_row(course_key, industry, duration, video_file="v001.mp4", title="Title"):
    return {
        "Course Key": course_key,
        "Industry": industry,
        "Duration (Minutes)": duration,
        "Video File Name": video_file,
        "Video Title (Lecture Title)": title,
        "Module Name": "Module 2",
    }


def test_group_videos_by_course_single_group():
    """Two rows with the same key/industry/duration end up in one group."""
    rows = [
        _make_row("course-v1:ORG+NUM+RUN", "Healthcare", "10", "v001.mp4", "Intro"),
        _make_row("course-v1:ORG+NUM+RUN", "Healthcare", "10", "v002.mp4", "Concepts"),
    ]
    groups = group_videos_by_course(rows)

    assert len(groups) == 1
    key = ("course-v1:ORG+NUM+RUN", "Healthcare", "10")
    assert len(groups[key]) == 2  # noqa: PLR2004


def test_group_videos_by_course_multiple_industries():
    """Rows with different industries produce separate groups."""
    rows = [
        _make_row("course-v1:ORG+NUM+RUN", "Healthcare", "10"),
        _make_row("course-v1:ORG+NUM+RUN", "Finance", "10"),
        _make_row("course-v1:ORG+NUM+RUN", "Energy", "long"),
        _make_row("course-v1:ORG+NUM+RUN", "Original industry", "10"),
    ]
    groups = group_videos_by_course(rows)

    assert len(groups) == 4  # noqa: PLR2004


def test_group_videos_by_course_multiple_source_courses():
    """Rows from different source course keys produce separate groups."""
    rows = [
        _make_row("course-v1:ORG+UAI.2+RUN", "Healthcare", "10"),
        _make_row("course-v1:ORG+UAI.3+RUN", "Healthcare", "10"),
    ]
    groups = group_videos_by_course(rows)

    assert len(groups) == 2  # noqa: PLR2004
