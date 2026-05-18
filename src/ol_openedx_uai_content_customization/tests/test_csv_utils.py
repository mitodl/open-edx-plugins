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


def test_parse_csv_returns_list_of_dicts(tmp_path):
    """Each row in the CSV is returned as a dict keyed by column header."""
    csv_text = "name,video_id\nv004_h264.mp4,abc-123\nv005_h264.mp4,def-456\n"
    csv_file = tmp_path / "assets.csv"
    csv_file.write_text(csv_text)

    rows, fieldnames = parse_csv(str(csv_file))

    assert len(rows) == 2  # noqa: PLR2004
    assert rows[0]["name"] == "v004_h264.mp4"
    assert rows[0]["video_id"] == "abc-123"
    assert fieldnames == ["name", "video_id"]


def test_parse_csv_empty_file(tmp_path):
    """A CSV with only a header row returns an empty row list but keeps the headers."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("name,video_id\n")

    rows, fieldnames = parse_csv(str(csv_file))

    assert rows == []
    assert fieldnames == ["name", "video_id"]


@pytest.mark.parametrize(
    ("fieldnames", "required", "should_raise"),
    [
        (["name", "video_id"], ["name", "video_id"], False),
        (["name"], ["name", "video_id"], True),
        ([], ["name", "video_id"], True),
    ],
)
def test_validate_csv_columns(fieldnames, required, should_raise):
    """Validate required-column checks for complete, partial, and empty headers."""
    if should_raise:
        with pytest.raises(ValueError, match="missing required columns"):
            validate_csv_columns(fieldnames, required, "test CSV")
        return

    validate_csv_columns(fieldnames, required, "test CSV")


@pytest.mark.parametrize(
    ("rows", "expected"),
    [
        (
            [
                {"name": "v004_h264.mp4", "video_id": "abc-123"},
                {"name": "v005_h264.mp4", "video_id": "def-456"},
            ],
            {
                "v004_h264.mp4": "abc-123",
                "v005_h264.mp4": "def-456",
            },
        ),
        ([], {}),
    ],
)
def test_build_video_id_map(rows, expected):
    """Map video asset rows to edX video IDs."""
    assert build_video_id_map(rows) == expected


@pytest.mark.parametrize(
    ("duration_value", "expected"),
    [
        ("long", "F"),
        ("Long", "F"),
        ("short", "S"),
        ("Short", "S"),
    ],
)
def test_resolve_duration_code(duration_value, expected):
    """Parametrised check that duration strings map to the correct S/F code."""
    assert resolve_duration_code(duration_value) == expected


def test_resolve_duration_code_unknown_raises():
    """An unrecognised duration string raises ValueError."""
    with pytest.raises(ValueError, match="Unrecognised duration value"):
        resolve_duration_code("unknown_value")


@pytest.mark.parametrize(
    ("orig_key", "industry", "duration", "expected"),
    [
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Healthcare",
            "short",
            "course-v1:UAI_SOURCE+UAI.2.S.HC+1T2026",
        ),
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Healthcare",
            "long",
            "course-v1:UAI_SOURCE+UAI.2.F.HC+1T2026",
        ),
        (
            "course-v1:UAI_SOURCE+UAI.2+1T2026",
            "Finance",
            "short",
            "course-v1:UAI_SOURCE+UAI.2.S.F+1T2026",
        ),
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Energy",
            "long",
            "course-v1:UAI_SOURCE+UAI.3.F.E+1T2026",
        ),
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Original industry",
            "short",
            "course-v1:UAI_SOURCE+UAI.3.S+1T2026",
        ),
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
            "course-v1:UAI_SOURCE+UAI.2+1T2026", "Unknown Industry", "short"
        )


def _make_row(course_key, industry, duration, video_file="v001.mp4", title="Title"):
    return {
        "course_key": course_key,
        "industry": industry,
        "duration": duration,
        "video_file_name": video_file,
        "video_title": title,
        "module_name": "Module 2",
    }


@pytest.mark.parametrize(
    ("rows", "expected_group_count", "expected_group_sizes"),
    [
        (
            [
                _make_row(
                    "course-v1:ORG+NUM+RUN",
                    "Healthcare",
                    "short",
                    "v001.mp4",
                    "Intro",
                ),
                _make_row(
                    "course-v1:ORG+NUM+RUN",
                    "Healthcare",
                    "short",
                    "v002.mp4",
                    "Concepts",
                ),
            ],
            1,
            {("course-v1:ORG+NUM+RUN", "Healthcare", "short"): 2},
        ),
        (
            [
                _make_row("course-v1:ORG+NUM+RUN", "Healthcare", "short"),
                _make_row("course-v1:ORG+NUM+RUN", "Finance", "short"),
                _make_row("course-v1:ORG+NUM+RUN", "Energy", "long"),
                _make_row("course-v1:ORG+NUM+RUN", "Original industry", "short"),
            ],
            4,
            {},
        ),
        (
            [
                _make_row("course-v1:ORG+UAI.2+RUN", "Healthcare", "short"),
                _make_row("course-v1:ORG+UAI.3+RUN", "Healthcare", "short"),
            ],
            2,
            {},
        ),
    ],
)
def test_group_videos_by_course(rows, expected_group_count, expected_group_sizes):
    """Group rows by source course, industry, and duration."""
    groups = group_videos_by_course(rows)

    assert len(groups) == expected_group_count
    for key, size in expected_group_sizes.items():
        assert len(groups[key]) == size
