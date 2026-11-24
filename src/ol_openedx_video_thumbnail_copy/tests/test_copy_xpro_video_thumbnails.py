"""Tests for the copy_xpro_video_thumbnails management command."""

from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from ol_openedx_video_thumbnail_copy.thumbnails import CopyResult
from opaque_keys.edx.keys import CourseKey

COMMAND = "copy_xpro_video_thumbnails"
COURSE_ID = "course-v1:xPRO+T1+R1"
_MODULE = (
    "ol_openedx_video_thumbnail_copy.management.commands.copy_xpro_video_thumbnails"
)


@pytest.fixture
def mock_copy(mocker):
    """Replace the copy function the command calls."""
    return mocker.patch(f"{_MODULE}.copy_course_thumbnails")


def test_invalid_course_key_raises():
    """A malformed course key is rejected."""
    with pytest.raises(CommandError, match="Invalid course key"):
        call_command(COMMAND, "not-a-key", stdout=StringIO())


@override_settings(OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL=None)
def test_no_source_url_raises(mock_copy):
    """Without a flag or a setting, the command refuses to run."""
    with pytest.raises(CommandError, match="source base URL"):
        call_command(COMMAND, COURSE_ID, stdout=StringIO())
    mock_copy.assert_not_called()


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_setting_used_when_no_flag(mock_copy):
    """The setting supplies the source URL when no flag is given."""
    mock_copy.return_value = CopyResult()

    call_command(COMMAND, COURSE_ID, stdout=StringIO())

    mock_copy.assert_called_once_with(
        CourseKey.from_string(COURSE_ID), "https://from-setting/media/", dry_run=False
    )


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_flag_overrides_setting_and_passes_dry_run(mock_copy):
    """--source-base-url wins over the setting and --dry-run is passed on."""
    mock_copy.return_value = CopyResult()

    call_command(
        COMMAND,
        COURSE_ID,
        "--source-base-url",
        "https://from-flag/media/",
        "--dry-run",
        stdout=StringIO(),
    )

    mock_copy.assert_called_once_with(
        CourseKey.from_string(COURSE_ID), "https://from-flag/media/", dry_run=True
    )


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_prints_counts_and_missing_keys(mock_copy):
    """The summary shows each count and lists the missing keys."""
    mock_copy.return_value = CopyResult(
        copied=["video-images/a.png"], skipped=[], missing=["video-images/m.png"]
    )
    out = StringIO()

    call_command(COMMAND, COURSE_ID, stdout=out)

    output = out.getvalue()
    assert "Copied: 1" in output
    assert "Skipped: 0" in output
    assert "Missing: 1" in output
    assert "video-images/m.png" in output
    assert "[dry run]" not in output


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_dry_run_output_is_labelled(mock_copy):
    """A dry run's summary says so."""
    mock_copy.return_value = CopyResult(copied=["video-images/a.png"])
    out = StringIO()

    call_command(COMMAND, COURSE_ID, "--dry-run", stdout=out)

    assert "[dry run] Copied: 1" in out.getvalue()


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_warns_when_course_has_no_thumbnails(mock_copy):
    """An unknown or wrong course key doesn't look like a successful run."""
    mock_copy.return_value = CopyResult()
    out = StringIO()

    call_command(COMMAND, COURSE_ID, stdout=out)

    assert "No video thumbnails found for course-v1:xPRO+T1+R1" in out.getvalue()


@override_settings(
    OL_VIDEO_THUMBNAIL_COPY_SOURCE_BASE_URL="https://from-setting/media/"
)
def test_no_warning_when_thumbnails_found(mock_copy):
    """The warning only shows when the course had no thumbnails at all."""
    mock_copy.return_value = CopyResult(skipped=["video-images/a.png"])
    out = StringIO()

    call_command(COMMAND, COURSE_ID, stdout=out)

    assert "No video thumbnails found" not in out.getvalue()
