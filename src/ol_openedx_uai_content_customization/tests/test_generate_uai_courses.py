"""Tests for the generate_uai_courses management command."""

from io import StringIO
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from xmodule.modulestore.exceptions import DuplicateCourseError

CUSTOMIZED_CSV_CONTENT = (
    "Course Key,Industry,Duration (Minutes),"
    "Video File Name,Video Title (Lecture Title),Module Name\n"
    "course-v1:UAI_SOURCE+UAI.2+1T2026,Healthcare,10,"
    "v004_h264.mp4,Machine Learning Concepts,Module 2\n"
    "course-v1:UAI_SOURCE+UAI.2+1T2026,Finance,10,"
    "v005_h264.mp4,Machine Learning Concepts,Module 2\n"
    "course-v1:UAI_SOURCE+UAI.3+1T2026,Original industry,long,"
    "v011_h264.mp4,Data Analytics,Module 3\n"
)

VIDEO_ASSETS_CSV_CONTENT = (
    "Name,Video ID\n"
    "v004_h264.mp4,aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa\n"
    "v005_h264.mp4,bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb\n"
    "v011_h264.mp4,cccccccc-3333-3333-3333-cccccccccccc\n"
)

# Base patch path for all helpers imported into the management command module.
_CMD = "ol_openedx_uai_content_customization.management.commands.generate_uai_courses"

# Expected number of unique course variants in the test CSV.
EXPECTED_COURSE_COUNT = 3


@pytest.fixture
def csv_files(tmp_path):
    """Write sample CSVs to tmp_path and return their paths."""
    customized = tmp_path / "customized.csv"
    customized.write_text(CUSTOMIZED_CSV_CONTENT)
    assets = tmp_path / "video_assets.csv"
    assets.write_text(VIDEO_ASSETS_CSV_CONTENT)
    return str(customized), str(assets)


@pytest.fixture
def mock_user(db):  # noqa: ARG001
    """Create and return a minimal User so the user-existence check passes."""
    User = get_user_model()
    return User.objects.create_user(username="studio_worker", password="x")  # noqa: S106


# ---------------------------------------------------------------------------
# Helpers — keep tests DRY
# ---------------------------------------------------------------------------


def _all_modulestore_mocks():
    """Return a list of (patch_path, kwargs) pairs for all modulestore helpers."""
    return [
        (f"{_CMD}.create_course_in_modulestore", {"return_value": mock.Mock()}),
        (f"{_CMD}.create_section", {"return_value": mock.Mock()}),
        (f"{_CMD}.create_subsection", {"return_value": mock.Mock()}),
        (f"{_CMD}.create_unit", {"return_value": mock.Mock()}),
        (f"{_CMD}.create_video_block", {}),
        (f"{_CMD}.publish_course", {}),
        (f"{_CMD}.course_bulk_operations", {}),
        (f"{_CMD}.initialize_course_permissions", {}),
    ]


# ---------------------------------------------------------------------------
# Dry-run mode — no modulestore calls should occur
# ---------------------------------------------------------------------------


def test_dry_run_prints_summary_without_creating_courses(csv_files, mock_user):  # noqa: ARG001
    customized_csv, assets_csv = csv_files
    out = StringIO()

    with mock.patch(f"{_CMD}.create_course_in_modulestore") as mock_create:
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv,
            video_assets_csv=assets_csv,
            dry_run=True,
            stdout=out,
        )
        mock_create.assert_not_called()

    output = out.getvalue()
    assert "DRY RUN" in output
    assert "course-v1:UAI_SOURCE+UAI.2.S.HC+1T2026" in output
    assert "course-v1:UAI_SOURCE+UAI.2.S.F+1T2026" in output
    assert "course-v1:UAI_SOURCE+UAI.3.F+1T2026" in output


# ---------------------------------------------------------------------------
# Full run — verify modulestore helpers are called correctly
# ---------------------------------------------------------------------------


def test_creates_correct_number_of_courses(csv_files, mock_user):  # noqa: ARG001
    customized_csv, assets_csv = csv_files

    with (
        mock.patch(
            f"{_CMD}.create_course_in_modulestore", return_value=mock.Mock()
        ) as mock_create_course,
        mock.patch(
            f"{_CMD}.create_section", return_value=mock.Mock()
        ) as mock_create_section,
        mock.patch(
            f"{_CMD}.create_subsection", return_value=mock.Mock()
        ) as mock_create_subsection,
        mock.patch(f"{_CMD}.create_unit", return_value=mock.Mock()) as mock_create_unit,
        mock.patch(f"{_CMD}.create_video_block") as mock_create_video,
        mock.patch(f"{_CMD}.publish_course"),
        mock.patch(f"{_CMD}.course_bulk_operations"),
        mock.patch(f"{_CMD}.initialize_course_permissions"),
    ):
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv,
            video_assets_csv=assets_csv,
        )

    # 3 unique (course_key, industry, duration) groups → 3 course creation calls
    assert mock_create_course.call_count == EXPECTED_COURSE_COUNT
    # Each course gets exactly one "Lectures" section
    assert mock_create_section.call_count == EXPECTED_COURSE_COUNT
    # One subsection per video row (3 video rows total)
    assert mock_create_subsection.call_count == EXPECTED_COURSE_COUNT
    assert mock_create_unit.call_count == EXPECTED_COURSE_COUNT
    assert mock_create_video.call_count == EXPECTED_COURSE_COUNT


def test_course_keys_are_correct(csv_files, mock_user):  # noqa: ARG001
    customized_csv, assets_csv = csv_files
    created_keys = []

    def capture_course(org, number, run, display_name, user_id):  # noqa: ARG001
        created_keys.append(f"course-v1:{org}+{number}+{run}")
        return mock.Mock()

    with (
        mock.patch(f"{_CMD}.create_course_in_modulestore", side_effect=capture_course),
        mock.patch(f"{_CMD}.create_section", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_subsection", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_unit", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_video_block"),
        mock.patch(f"{_CMD}.publish_course"),
        mock.patch(f"{_CMD}.course_bulk_operations"),
        mock.patch(f"{_CMD}.initialize_course_permissions"),
    ):
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv,
            video_assets_csv=assets_csv,
        )

    assert "course-v1:UAI_SOURCE+UAI.2.S.HC+1T2026" in created_keys
    assert "course-v1:UAI_SOURCE+UAI.2.S.F+1T2026" in created_keys
    assert "course-v1:UAI_SOURCE+UAI.3.F+1T2026" in created_keys


def test_unmapped_video_is_skipped_with_warning(tmp_path, mock_user):  # noqa: ARG001
    """A video whose file name has no match in the assets CSV should be skipped."""
    customized = tmp_path / "customized.csv"
    customized.write_text(
        "Course Key,Industry,Duration (Minutes),Video File Name,"
        "Video Title (Lecture Title),Module Name\n"
        "course-v1:UAI_SOURCE+UAI.2+1T2026,Healthcare,10,"
        "MISSING_FILE.mp4,Some Title,Module 2\n"
    )
    assets = tmp_path / "assets.csv"
    assets.write_text("Name,Video ID\nv004_h264.mp4,abc-123\n")

    out = StringIO()

    with (
        mock.patch(f"{_CMD}.create_course_in_modulestore", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_section", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_subsection", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_unit", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.create_video_block") as mock_video,
        mock.patch(f"{_CMD}.publish_course"),
        mock.patch(f"{_CMD}.course_bulk_operations"),
        mock.patch(f"{_CMD}.initialize_course_permissions"),
    ):
        call_command(
            "generate_uai_courses",
            customized_csv=str(customized),
            video_assets_csv=str(assets),
            stdout=out,
        )
        mock_video.assert_not_called()

    assert "Warning" in out.getvalue() or "MISSING_FILE" in out.getvalue()


def test_duplicate_course_is_skipped_with_warning(csv_files, mock_user):  # noqa: ARG001
    """DuplicateCourseError should be caught and the course skipped, not crash."""
    customized_csv, assets_csv = csv_files
    out = StringIO()

    with (
        mock.patch(
            f"{_CMD}.create_course_in_modulestore",
            side_effect=DuplicateCourseError("x", "x"),
        ),
        mock.patch(f"{_CMD}.course_bulk_operations"),
        mock.patch(f"{_CMD}.initialize_course_permissions"),
    ):
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv,
            video_assets_csv=assets_csv,
            stdout=out,
        )

    output = out.getvalue()
    assert "already exists" in output
    assert "Skipped" in output or "skipped" in output.lower()


def test_missing_csv_raises_error(mock_user):  # noqa: ARG001
    with pytest.raises((CommandError, FileNotFoundError)):
        call_command(
            "generate_uai_courses",
            customized_csv="/nonexistent/path.csv",
            video_assets_csv="/also/nonexistent.csv",
        )


def test_invalid_user_id_raises_error(csv_files):
    """Passing a non-existent username should raise CommandError before any writes."""
    customized_csv, assets_csv = csv_files
    with pytest.raises(CommandError, match="No user found with username"):
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv,
            video_assets_csv=assets_csv,
            username="nonexistent_user",
        )


def test_unknown_industry_is_skipped_with_warning(tmp_path, mock_user):  # noqa: ARG001
    """A row with an unrecognised industry should be skipped with a warning."""
    customized = tmp_path / "customized.csv"
    customized.write_text(
        "Course Key,Industry,Duration (Minutes),Video File Name,"
        "Video Title (Lecture Title),Module Name\n"
        "course-v1:UAI_SOURCE+UAI.2+1T2026,UnknownSector,10,"
        "v004_h264.mp4,Some Title,Module 2\n"
    )
    assets = tmp_path / "assets.csv"
    assets.write_text("Name,Video ID\nv004_h264.mp4,abc-123\n")

    out = StringIO()

    with mock.patch(f"{_CMD}.create_course_in_modulestore") as mock_create:
        call_command(
            "generate_uai_courses",
            customized_csv=str(customized),
            video_assets_csv=str(assets),
            stdout=out,
        )
        mock_create.assert_not_called()

    assert "Skipping" in out.getvalue() or "skipping" in out.getvalue().lower()
