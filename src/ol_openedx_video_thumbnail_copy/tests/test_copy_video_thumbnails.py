"""Tests for the copy_video_thumbnails management command."""

from io import StringIO

import pytest
import responses
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from django.core.management import call_command
from edxval.models import CourseVideo, Video, VideoImage

COMMAND = "copy_video_thumbnails"
COURSE_ID = "course-v1:OL+T1+R1"
BASE = "https://source-edxapp-storage.s3.amazonaws.com/media/"
PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture
def storage(mocker):
    """Swap edx-val's image storage for an in-memory one."""
    in_memory = InMemoryStorage()
    mocker.patch(
        "ol_openedx_video_thumbnail_copy.management.commands."
        "copy_video_thumbnails.get_video_image_storage",
        return_value=in_memory,
    )
    return in_memory


def make_image(edx_video_id, name):
    """Create the edx-val rows a course import leaves behind for one video."""
    video = Video.objects.create(edx_video_id=edx_video_id, status="upload", duration=0)
    course_video = CourseVideo.objects.create(video=video, course_id=COURSE_ID)
    VideoImage.create_or_update(course_video, file_name=name)


def run_command():
    """Run the command and return its stdout and stderr."""
    out, err = StringIO(), StringIO()
    call_command(COMMAND, COURSE_ID, BASE, stdout=out, stderr=err)
    return out.getvalue(), err.getvalue()


@pytest.mark.django_db
@responses.activate
def test_copies_missing_thumbnail_under_same_key(storage):
    """A missing thumbnail is downloaded and saved under its key.

    The "#" is part of the object name, so it must be URL-encoded.
    """
    make_image("vid-1", "video-images/frame#1.png")
    responses.get(
        BASE + "video-images/frame%231.png", body=PNG, content_type="image/png"
    )

    out, _ = run_command()

    assert storage.open("video-images/frame#1.png").read() == PNG
    assert "copied video-images/frame#1.png" in out


@pytest.mark.django_db
@responses.activate
def test_skips_existing_without_request(storage):
    """A thumbnail already in local storage is left alone and not fetched."""
    make_image("vid-1", "video-images/a.png")
    storage.save("video-images/a.png", ContentFile(b"LOCAL"))

    out, _ = run_command()

    assert len(responses.calls) == 0
    assert storage.open("video-images/a.png").read() == b"LOCAL"
    assert "skipped video-images/a.png" in out


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "source",
    [
        pytest.param({"status": 404}, id="not-found"),
        # A 200 that isn't an image usually means a wrong base URL.
        pytest.param(
            {"body": "<html></html>", "content_type": "text/html"}, id="not-an-image"
        ),
    ],
)
def test_failed_or_non_image_response_is_not_saved(storage, source):
    """Nothing is saved, so a later run with the right URL still copies it."""
    make_image("vid-1", "video-images/a.png")
    responses.get(BASE + "video-images/a.png", **source)

    _, err = run_command()

    assert not storage.exists("video-images/a.png")
    assert "missing video-images/a.png" in err


@pytest.mark.django_db
@responses.activate
def test_error_on_one_key_does_not_stop_the_rest(storage, mocker):
    """A key that always fails (e.g. a traversal key from OLX) is skipped over."""
    make_image("vid-1", "video-images/../../x.png")
    make_image("vid-2", "video-images/ok.png")
    responses.get(BASE + "video-images/ok.png", body=PNG, content_type="image/png")
    real_exists = storage.exists

    def exists(name):
        if ".." in name:
            raise SuspiciousFileOperation(name)
        return real_exists(name)

    mocker.patch.object(storage, "exists", side_effect=exists)

    out, err = run_command()

    assert "missing video-images/../../x.png" in err
    assert "copied video-images/ok.png" in out
    assert storage.exists("video-images/ok.png")
