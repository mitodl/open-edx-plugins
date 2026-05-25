"""Tests for the generate_uai_course_versions management command."""

from io import StringIO
from unittest import mock

import pytest
from common.djangoapps.student.tests.factories import UserFactory
from django.core.management import call_command
from django.core.management.base import CommandError
from ol_openedx_uai_content_customization.constants import (
    BLOCK_TYPE_CHAPTER,
    BLOCK_TYPE_HTML,
    BLOCK_TYPE_SEQUENTIAL,
    BLOCK_TYPE_VERTICAL,
    BLOCK_TYPE_VIDEO,
)
from xmodule.modulestore.exceptions import DuplicateCourseError

PROCESSED_VIDEOS_CSV_CONTENT = (
    "course_key,industry,duration,"
    "video_file_name,video_title,module_name,course_intro\n"
    "course-v1:UAI_SOURCE+UAI.2+1T2026,Healthcare,short,"
    "v004_h264.mp4,Machine Learning Concepts,Module 2,<p>Healthcare short intro</p>\n"
    "course-v1:UAI_SOURCE+UAI.2+1T2026,Finance,short,"
    "v005_h264.mp4,Machine Learning Concepts,Module 2,<p>Finance short intro</p>\n"
    "course-v1:UAI_SOURCE+UAI.3+1T2026,Original industry,long,"
    "v011_h264.mp4,Data Analytics,Module 3,<p>Original long intro</p>\n"
)

EDX_VIDEOS_CSV_CONTENT = (
    "name,video_id\n"
    "v004_h264.mp4,aaaaaaaa-1111-1111-1111-aaaaaaaaaaaa\n"
    "v005_h264.mp4,bbbbbbbb-2222-2222-2222-bbbbbbbbbbbb\n"
    "v011_h264.mp4,cccccccc-3333-3333-3333-cccccccccccc\n"
)

_CMD = "ol_openedx_uai_content_customization.management.commands.generate_uai_course_versions"  # noqa: E501
EXPECTED_COURSE_COUNT = 6
EXPECTED_NEW_COURSE_KEYS = (
    "course-v1:UAI_SOURCE+UAI.2.S.HC+1T2026",
    "course-v1:UAI_SOURCE+UAI.2.S.F+1T2026",
    "course-v1:UAI_SOURCE+UAI.3.F+1T2026",
)
EXPECTED_BLOCK_TYPES = (
    BLOCK_TYPE_CHAPTER,
    BLOCK_TYPE_SEQUENTIAL,
    BLOCK_TYPE_VERTICAL,
    BLOCK_TYPE_VIDEO,
    BLOCK_TYPE_HTML,
)


@pytest.fixture
def csv_files(tmp_path):
    """Write sample CSVs to tmp_path and return their paths."""
    processed_videos = tmp_path / "processed_videos.csv"
    processed_videos.write_text(PROCESSED_VIDEOS_CSV_CONTENT)
    edx_videos = tmp_path / "edx_videos.csv"
    edx_videos.write_text(EDX_VIDEOS_CSV_CONTENT)
    return str(processed_videos), str(edx_videos)


@pytest.fixture
def mock_user(db):  # noqa: ARG001
    """Create and return a studio_worker user so the user-existence check passes."""
    return UserFactory.create(username="studio_worker")


def _modulestore_mock():
    """
    Return a mock for the ``modulestore`` callable imported by the command.

    ``has_course`` returns True by default so source-key validation passes in
    the majority of tests that are not testing that code path.
    """
    m = mock.MagicMock()
    m.return_value.has_course.return_value = True
    return m


@pytest.mark.parametrize("expected_key", EXPECTED_NEW_COURSE_KEYS)
def test_dry_run_prints_summary_without_creating_courses(
    csv_files, mock_user, expected_key
):
    _ = mock_user
    processed_videos_csv, edx_videos_csv = csv_files
    out = StringIO()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(f"{_CMD}.get_or_clone_course_in_modulestore") as mock_clone,
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
            dry_run=True,
            stdout=out,
        )
        mock_clone.assert_not_called()

    output = out.getvalue()
    assert "DRY RUN" in output
    assert expected_key in output


def test_creates_correct_number_of_courses(csv_files, mock_user):  # noqa: ARG001
    processed_videos_csv, edx_videos_csv = csv_files

    block_by_type = {
        BLOCK_TYPE_CHAPTER: mock.Mock(),
        BLOCK_TYPE_SEQUENTIAL: mock.Mock(),
        BLOCK_TYPE_VERTICAL: mock.Mock(),
        BLOCK_TYPE_VIDEO: mock.Mock(),
        BLOCK_TYPE_HTML: mock.Mock(),
    }

    def mock_create_content_block(parent, block_type, display_name, user_id, **kwargs):  # noqa: ARG001
        return block_by_type[block_type]

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore", return_value=mock.Mock()
        ) as mock_clone,
        mock.patch(f"{_CMD}.delete_course_sections") as mock_delete_sections,
        mock.patch(
            f"{_CMD}.create_content_block", side_effect=mock_create_content_block
        ) as mock_create_content_block_call,
        mock.patch(f"{_CMD}.save_video_block_with_edx_video_id"),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
        )

    assert mock_clone.call_count == EXPECTED_COURSE_COUNT
    assert mock_delete_sections.call_count == EXPECTED_COURSE_COUNT

    create_calls = mock_create_content_block_call.call_args_list
    assert len(create_calls) == EXPECTED_COURSE_COUNT * 8

    counts_by_type = dict.fromkeys(EXPECTED_BLOCK_TYPES, 0)
    for call in create_calls:
        block_type = call.args[1]
        counts_by_type[block_type] += 1

    assert counts_by_type[BLOCK_TYPE_CHAPTER] == EXPECTED_COURSE_COUNT * 2
    assert counts_by_type[BLOCK_TYPE_SEQUENTIAL] == EXPECTED_COURSE_COUNT * 2
    assert counts_by_type[BLOCK_TYPE_VERTICAL] == EXPECTED_COURSE_COUNT * 2
    assert counts_by_type[BLOCK_TYPE_VIDEO] == EXPECTED_COURSE_COUNT
    assert counts_by_type[BLOCK_TYPE_HTML] == EXPECTED_COURSE_COUNT


@pytest.mark.parametrize("expected_key", EXPECTED_NEW_COURSE_KEYS)
def test_course_keys_are_correct(csv_files, mock_user, expected_key):  # noqa: ARG001
    processed_videos_csv, edx_videos_csv = csv_files
    created_keys = []

    def capture_clone(source_key, org, number, run, display_name, user_id):  # noqa: ARG001, PLR0913
        created_keys.append(f"course-v1:{org}+{number}+{run}")
        return mock.Mock()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore", side_effect=capture_clone
        ),
        mock.patch(f"{_CMD}.delete_course_sections"),
        mock.patch(f"{_CMD}.create_content_block", return_value=mock.Mock()),
        mock.patch(f"{_CMD}.save_video_block_with_edx_video_id"),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
        )

    assert expected_key in created_keys


def test_unmapped_video_is_skipped_with_warning(tmp_path, mock_user):  # noqa: ARG001
    """A video whose file name has no match in the edX videos CSV should be skipped."""
    processed_videos = tmp_path / "processed_videos.csv"
    processed_videos.write_text(
        "course_key,industry,duration,video_file_name,"
        "video_title,module_name,course_intro\n"
        "course-v1:UAI_SOURCE+UAI.2+1T2026,Healthcare,short,"
        "MISSING_FILE.mp4,Some Title,Module 2,<p>Missing mapping intro</p>\n"
    )
    edx_videos = tmp_path / "edx_videos.csv"
    edx_videos.write_text("name,video_id\nv004_h264.mp4,abc-123\n")

    out = StringIO()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore", return_value=mock.Mock()
        ),
        mock.patch(f"{_CMD}.delete_course_sections"),
        mock.patch(f"{_CMD}.create_content_block") as mock_create_content_block,
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=str(processed_videos),
            edx_videos_csv=str(edx_videos),
            stdout=out,
        )

    video_calls = [
        call
        for call in mock_create_content_block.call_args_list
        if call.args[1] == BLOCK_TYPE_VIDEO
    ]
    assert not video_calls

    assert "Warning" in out.getvalue() or "MISSING_FILE" in out.getvalue()


def test_duplicate_course_is_skipped_with_warning(csv_files, mock_user):  # noqa: ARG001
    """DuplicateCourseError should be caught and the course skipped, not crash."""
    processed_videos_csv, edx_videos_csv = csv_files
    out = StringIO()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore",
            side_effect=DuplicateCourseError("x", "x"),
        ),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
            stdout=out,
        )

    output = out.getvalue()
    assert "already exists" in output
    assert "Skipped" in output or "skipped" in output.lower()


def test_missing_csv_raises_error(mock_user):  # noqa: ARG001
    with pytest.raises((CommandError, FileNotFoundError)):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv="/nonexistent/path.csv",
            edx_videos_csv="/also/nonexistent.csv",
        )


def test_invalid_user_id_raises_error(csv_files, db):  # noqa: ARG001
    """Passing a non-existent username should raise CommandError before any writes."""
    processed_videos_csv, edx_videos_csv = csv_files
    with pytest.raises(CommandError, match="No user found with username"):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
            username="nonexistent_user",
        )


def test_unknown_industry_is_skipped_with_warning(tmp_path, mock_user):  # noqa: ARG001
    """A row with an unrecognised industry should be skipped with a warning."""
    processed_videos = tmp_path / "processed_videos.csv"
    processed_videos.write_text(
        "course_key,industry,duration,video_file_name,"
        "video_title,module_name,course_intro\n"
        "course-v1:UAI_SOURCE+UAI.2+1T2026,UnknownSector,short,"
        "v004_h264.mp4,Some Title,Module 2,<p>Unknown sector intro</p>\n"
    )
    edx_videos = tmp_path / "edx_videos.csv"
    edx_videos.write_text("name,video_id\nv004_h264.mp4,abc-123\n")

    out = StringIO()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(f"{_CMD}.get_or_clone_course_in_modulestore") as mock_clone,
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=str(processed_videos),
            edx_videos_csv=str(edx_videos),
            stdout=out,
        )
        mock_clone.assert_not_called()

    assert "Skipping" in out.getvalue() or "skipping" in out.getvalue().lower()


def test_source_course_not_in_modulestore_raises_error(csv_files, mock_user):  # noqa: ARG001
    """CommandError is raised before any writes when a source course is absent."""
    processed_videos_csv, edx_videos_csv = csv_files

    store_mock = _modulestore_mock()
    store_mock.return_value.has_course.return_value = False

    with (
        mock.patch(f"{_CMD}.modulestore", store_mock),
        mock.patch(f"{_CMD}.get_or_clone_course_in_modulestore") as mock_clone,
        pytest.raises(CommandError, match="not found in the modulestore"),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
        )

    mock_clone.assert_not_called()


def test_delete_sections_called_before_create_chapter(csv_files, mock_user):  # noqa: ARG001
    """delete_course_sections must run before chapter creation in each course."""
    processed_videos_csv, edx_videos_csv = csv_files
    call_order = []

    def record_delete(course, user_id):  # noqa: ARG001
        call_order.append("delete")

    def record_create_content_block(
        _parent, block_type, _display_name, _user_id, **_kwargs
    ):
        if block_type == BLOCK_TYPE_CHAPTER:
            call_order.append("create_chapter")
        return mock.Mock()

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore", return_value=mock.Mock()
        ),
        mock.patch(f"{_CMD}.delete_course_sections", side_effect=record_delete),
        mock.patch(
            f"{_CMD}.create_content_block", side_effect=record_create_content_block
        ),
        mock.patch(f"{_CMD}.save_video_block_with_edx_video_id"),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=processed_videos_csv,
            edx_videos_csv=edx_videos_csv,
        )

    assert call_order.count("delete") == EXPECTED_COURSE_COUNT
    assert call_order.count("create_chapter") == EXPECTED_COURSE_COUNT
    for i in range(0, len(call_order), 2):
        assert call_order[i] == "delete", f"Expected delete at position {i}"
        assert call_order[i + 1] == "create_chapter", (
            f"Expected create_chapter at position {i + 1}"
        )


def test_skips_introduction_when_course_intro_missing(tmp_path, mock_user):  # noqa: ARG001
    """If no intro resolves for a variant, no HTML intro block should be created."""
    processed_videos = tmp_path / "processed_videos.csv"
    processed_videos.write_text(
        "course_key,industry,duration,video_file_name,"
        "video_title,module_name,course_intro\n"
        "course-v1:UAI_SOURCE+UAI.2+1T2026,Healthcare,short,"
        "v004_h264.mp4,Some Title,Module 2,\n"
    )
    edx_videos = tmp_path / "edx_videos.csv"
    edx_videos.write_text("name,video_id\nv004_h264.mp4,abc-123\n")

    with (
        mock.patch(f"{_CMD}.modulestore", _modulestore_mock()),
        mock.patch(
            f"{_CMD}.get_or_clone_course_in_modulestore", return_value=mock.Mock()
        ),
        mock.patch(f"{_CMD}.delete_course_sections"),
        mock.patch(f"{_CMD}.create_content_block") as mock_create_content_block,
        mock.patch(f"{_CMD}.save_video_block_with_edx_video_id"),
    ):
        call_command(
            "generate_uai_course_versions",
            processed_videos_csv=str(processed_videos),
            edx_videos_csv=str(edx_videos),
        )

    html_calls = [
        call
        for call in mock_create_content_block.call_args_list
        if call.args[1] == BLOCK_TYPE_HTML
    ]
    assert not html_calls
