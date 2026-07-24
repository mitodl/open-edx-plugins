"""Tests for ol_openedx_uai_content_customization csv_utils."""

from unittest import mock

import pytest
import requests
from ol_openedx_uai_content_customization.csv_utils import (
    build_course_intro_lookup,
    build_google_sheet_csv_export_url,
    build_new_course_key,
    fetch_csv_text,
    group_videos_by_course,
    is_google_sheets_url,
    is_url,
    normalize_course_intro,
    parse_csv,
    resolve_course_intro,
    resolve_duration_code,
    validate_csv_columns,
)


def test_parse_csv_returns_list_of_dicts(tmp_path):
    """Each row in the CSV is returned as a dict keyed by column header."""
    csv_text = (
        "video_file_name,edx_video_id\nv004_h264.mp4,abc-123\nv005_h264.mp4,def-456\n"
    )
    csv_file = tmp_path / "videos.csv"
    csv_file.write_text(csv_text)

    rows, fieldnames = parse_csv(str(csv_file))

    assert len(rows) == 2  # noqa: PLR2004
    assert rows[0]["video_file_name"] == "v004_h264.mp4"
    assert rows[0]["edx_video_id"] == "abc-123"
    assert fieldnames == ["video_file_name", "edx_video_id"]


def test_parse_csv_empty_file(tmp_path):
    """A CSV with only a header row returns an empty row list but keeps the headers."""
    csv_file = tmp_path / "empty.csv"
    csv_file.write_text("video_file_name,edx_video_id\n")

    rows, fieldnames = parse_csv(str(csv_file))

    assert rows == []
    assert fieldnames == ["video_file_name", "edx_video_id"]


@pytest.mark.parametrize(
    ("fieldnames", "required", "should_raise"),
    [
        (["name", "video_id"], ["name", "video_id"], False),
        (["Name", "Video_ID"], ["name", "video_id"], False),
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
    ("source", "expected"),
    [
        ("/path/to/file.csv", False),
        ("file.csv", False),
        ("https://docs.google.com/spreadsheets/d/abc123/edit", True),
        ("http://example.com/videos.csv", True),
    ],
)
def test_is_url(source, expected):
    """Only http(s) sources are treated as URLs; everything else is a local path."""
    assert is_url(source) is expected


@pytest.mark.parametrize(
    ("sheet_url", "expected"),
    [
        (
            "https://docs.google.com/spreadsheets/d/abc123/edit#gid=456",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=456",
        ),
        (
            "https://docs.google.com/spreadsheets/d/abc123/edit?usp=sharing",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=0",
        ),
        (
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=9",
            "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=9",
        ),
    ],
)
def test_build_google_sheet_csv_export_url(sheet_url, expected):
    """Share/edit links are converted to CSV export links; export links pass through."""
    assert build_google_sheet_csv_export_url(sheet_url) == expected


def test_build_google_sheet_csv_export_url_invalid_raises():
    """A URL without a recognisable spreadsheet ID raises ValueError."""
    with pytest.raises(ValueError, match="Could not find a spreadsheet ID"):
        build_google_sheet_csv_export_url("https://example.com/not-a-sheet")


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("https://docs.google.com/spreadsheets/d/abc123/edit#gid=0", True),
        ("https://docs.google.com/spreadsheets/d/abc123/export?format=csv", True),
        # Only the docs.google.com host is trusted, regardless of path shape.
        ("https://example.com/spreadsheets/d/abc123/export?format=csv", False),
        ("https://example.com/foo.csv", False),
        ("https://evil.com/export?output=csv", False),
        ("/path/to/file.csv", False),
    ],
)
def test_is_google_sheets_url(source, expected):
    """Only docs.google.com Sheets links are recognised — no other host."""
    assert is_google_sheets_url(source) is expected


def test_fetch_csv_text_direct_url_is_not_rewritten():
    """
    A non-Google direct CSV URL is fetched as-is, without raising ValueError.

    This is the case even when the URL happens to contain "/export" or
    "output=csv", proving such URLs are never mistaken for Google Sheets
    export links (which would let an operator target arbitrary hosts under
    the guise of Google Sheets support).
    """
    mock_response = mock.Mock()
    mock_response.text = "a,b\n1,2\n"
    mock_response.raise_for_status = mock.Mock()

    direct_url = "https://example.com/export?output=csv"
    with mock.patch(
        "ol_openedx_uai_content_customization.csv_utils.requests.get",
        return_value=mock_response,
    ) as mock_get:
        text = fetch_csv_text(direct_url)

    mock_get.assert_called_once_with(direct_url, timeout=30)
    assert text == "a,b\n1,2\n"


def test_parse_csv_from_google_sheet_url():
    """parse_csv fetches and parses CSV content from a Google Sheets URL."""
    csv_text = "video_file_name,edx_video_id\nv004_h264.mp4,abc-123\n"
    mock_response = mock.Mock()
    mock_response.text = csv_text
    mock_response.raise_for_status = mock.Mock()

    with mock.patch(
        "ol_openedx_uai_content_customization.csv_utils.requests.get",
        return_value=mock_response,
    ) as mock_get:
        rows, fieldnames = parse_csv(
            "https://docs.google.com/spreadsheets/d/abc123/edit#gid=0"
        )

    mock_get.assert_called_once_with(
        "https://docs.google.com/spreadsheets/d/abc123/export?format=csv&gid=0",
        timeout=30,
    )
    assert fieldnames == ["video_file_name", "edx_video_id"]
    assert rows == [{"video_file_name": "v004_h264.mp4", "edx_video_id": "abc-123"}]


def test_parse_csv_from_google_sheet_url_raises_on_http_error():
    """A non-2xx response while fetching the sheet propagates as a RequestException."""
    mock_response = mock.Mock()
    mock_response.raise_for_status.side_effect = requests.HTTPError("404")

    with (
        mock.patch(
            "ol_openedx_uai_content_customization.csv_utils.requests.get",
            return_value=mock_response,
        ),
        pytest.raises(requests.HTTPError),
    ):
        parse_csv("https://docs.google.com/spreadsheets/d/abc123/edit")


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
            "Original",
            "short",
            "course-v1:UAI_SOURCE+UAI.3.S+1T2026",
        ),
        (
            "course-v1:UAI_SOURCE+UAI.3+1T2026",
            "Original",
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
        "course_intro": "",
        "edx_video_id": "aaaaaaaa-0000-0000-0000-aaaaaaaaaaaa",
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
                _make_row("course-v1:ORG+NUM+RUN", "Original", "short"),
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


def test_resolve_course_intro_precedence_exact_overrides_industry_and_original():
    """Exact (course, industry, duration) intro should have highest precedence."""
    rows = [
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Original", "short"),
            "course_intro": "<p>Original fallback</p>",
        },
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Healthcare", "long"),
            "course_intro": "<p>Healthcare industry intro</p>",
        },
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Healthcare", "short"),
            "course_intro": "<p>Healthcare short intro</p>",
        },
    ]

    lookup = build_course_intro_lookup(rows)

    assert (
        resolve_course_intro(lookup, "course-v1:ORG+NUM+RUN", "Healthcare", "short")
        == "<p>Healthcare short intro</p>"
    )


def test_resolve_course_intro_industry_fallback_applies_across_durations():
    """Industry intro should apply when no duration-specific intro exists."""
    rows = [
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Healthcare", "long"),
            "course_intro": "<p>Healthcare generic intro</p>",
        }
    ]

    lookup = build_course_intro_lookup(rows)

    assert (
        resolve_course_intro(lookup, "course-v1:ORG+NUM+RUN", "Healthcare", "short")
        == "<p>Healthcare generic intro</p>"
    )
    assert (
        resolve_course_intro(lookup, "course-v1:ORG+NUM+RUN", "Healthcare", "long")
        == "<p>Healthcare generic intro</p>"
    )


def test_resolve_course_intro_original_industry_fallback_across_industries():
    """Original industry intro should be fallback for other industries."""
    rows = [
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Original", "short"),
            "course_intro": "<p>Original intro</p>",
        }
    ]

    lookup = build_course_intro_lookup(rows)

    assert (
        resolve_course_intro(lookup, "course-v1:ORG+NUM+RUN", "Finance", "long")
        == "<p>Original intro</p>"
    )


def test_build_course_intro_lookup_first_row_wins_for_conflicts():
    """When same lookup key appears more than once, first row should win."""
    rows = [
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Finance", "short"),
            "course_intro": "<p>First intro</p>",
        },
        {
            **_make_row("course-v1:ORG+NUM+RUN", "Finance", "short"),
            "course_intro": "<p>Second intro</p>",
        },
    ]

    lookup = build_course_intro_lookup(rows)

    assert (
        resolve_course_intro(lookup, "course-v1:ORG+NUM+RUN", "Finance", "short")
        == "<p>First intro</p>"
    )


def test_normalize_course_intro_keeps_html_as_is():
    """Existing HTML content should be stored without modification."""
    assert normalize_course_intro("<p>Already HTML</p>") == "<p>Already HTML</p>"


def test_normalize_course_intro_wraps_plain_text_in_paragraph():
    """Plain text should be wrapped in a paragraph tag and escaped."""
    assert normalize_course_intro("Hello & welcome") == "<p>Hello &amp; welcome</p>"
