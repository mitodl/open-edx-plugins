"""Tests for copying a course's video thumbnails from the source storage."""

from io import BytesIO

import pytest
import requests
import responses
from django.core.exceptions import SuspiciousFileOperation
from django.core.files.base import ContentFile
from django.core.files.storage import InMemoryStorage
from edxval.models import CourseVideo, Video, VideoImage
from ol_openedx_video_thumbnail_copy.thumbnails import (
    CopyResult,
    build_source_url,
    copy_course_thumbnails,
)
from opaque_keys.edx.keys import CourseKey
from PIL import Image

BASE = "https://xpro-qa-edxapp-storage.s3.amazonaws.com/media/"
COURSE = CourseKey.from_string("course-v1:xPRO+T1+R1")
OTHER_COURSE = "course-v1:xPRO+OTHER+R1"


def image_bytes(image_format):
    """Return a small, complete image encoded as ``image_format``."""
    buffer = BytesIO()
    Image.new("RGB", (16, 9), "red").save(buffer, image_format)
    return buffer.getvalue()


PNG = image_bytes("PNG")
BMP = image_bytes("BMP")


@pytest.fixture
def storage(mocker):
    """Swap edx-val's image storage for an in-memory one."""
    in_memory = InMemoryStorage()
    mocker.patch(
        "ol_openedx_video_thumbnail_copy.thumbnails.get_video_image_storage",
        return_value=in_memory,
    )
    return in_memory


def make_image(course_id, edx_video_id, name):
    """Create the edx-val rows a course import leaves behind for one video."""
    video = Video.objects.create(edx_video_id=edx_video_id, status="upload", duration=0)
    course_video = CourseVideo.objects.create(video=video, course_id=course_id)
    VideoImage.create_or_update(course_video, file_name=name)


@pytest.mark.django_db
@responses.activate
def test_copies_missing_image_under_same_key(storage):
    """A thumbnail missing locally is downloaded and saved under its key."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    responses.get(BASE + "video-images/a.png", body=PNG, content_type="image/png")

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.copied == ["video-images/a.png"]
    assert storage.open("video-images/a.png").read() == PNG


@pytest.mark.django_db
@responses.activate
def test_skips_existing_without_request(storage):
    """A thumbnail already in local storage is left alone and not fetched."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    storage.save("video-images/a.png", ContentFile(b"LEARN"))

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.skipped == ["video-images/a.png"]
    assert result.copied == []
    assert len(responses.calls) == 0
    assert storage.open("video-images/a.png").read() == b"LEARN"


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    "failure",
    [
        {"status": 404},
        {"status": 500},
        {"body": requests.ConnectionError()},
        {"body": requests.Timeout()},
    ],
)
def test_source_failure_is_missing_and_others_still_copy(storage, failure):
    """A failed download is reported as missing and does not stop the rest."""
    make_image(str(COURSE), "vid-1", "video-images/bad.png")
    make_image(str(COURSE), "vid-2", "video-images/ok.png")
    responses.get(BASE + "video-images/bad.png", **failure)
    responses.get(BASE + "video-images/ok.png", body=PNG, content_type="image/png")

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.missing == ["video-images/bad.png"]
    assert result.copied == ["video-images/ok.png"]
    assert not storage.exists("video-images/bad.png")


@pytest.mark.django_db
@responses.activate
@pytest.mark.usefixtures("storage")
def test_shared_key_copied_once():
    """Videos sharing one image key (course reruns) cause a single copy."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    make_image(str(COURSE), "vid-2", "video-images/a.png")
    responses.get(BASE + "video-images/a.png", body=PNG, content_type="image/png")

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.copied == ["video-images/a.png"]
    assert len(responses.calls) == 1


@pytest.mark.django_db
@responses.activate
def test_only_requested_course(storage):
    """Thumbnails of other courses are not touched."""
    make_image(OTHER_COURSE, "vid-9", "video-images/z.png")

    assert copy_course_thumbnails(COURSE, BASE) == CopyResult([], [], [])
    assert not storage.exists("video-images/z.png")


@pytest.mark.django_db
@responses.activate
@pytest.mark.usefixtures("storage")
def test_course_without_videos():
    """A course with no videos copies nothing."""
    assert copy_course_thumbnails(COURSE, BASE) == CopyResult([], [], [])
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
@pytest.mark.usefixtures("storage")
def test_blank_image_name_is_ignored():
    """A video without a thumbnail key is ignored."""
    make_image(str(COURSE), "vid-1", "")

    assert copy_course_thumbnails(COURSE, BASE) == CopyResult([], [], [])
    assert len(responses.calls) == 0


@pytest.mark.django_db
@responses.activate
def test_dry_run_downloads_nothing_writes_nothing(storage):
    """A dry run reports what would be copied without fetching or saving."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")

    result = copy_course_thumbnails(COURSE, BASE, dry_run=True)

    assert result.copied == ["video-images/a.png"]
    assert len(responses.calls) == 0
    assert not storage.exists("video-images/a.png")


@pytest.mark.parametrize("base", [BASE, BASE.rstrip("/")])
def test_build_source_url(base):
    """The base URL joins the key with exactly one slash."""
    assert build_source_url(base, "video-images/a.png") == (BASE + "video-images/a.png")


@pytest.mark.parametrize(
    ("key", "path"),
    [
        ("video-images/frame#1.png", "video-images/frame%231.png"),
        ("video-images/a?b.png", "video-images/a%3Fb.png"),
        ("video-images/50%25.png", "video-images/50%2525.png"),
        ("video-images/a b.png", "video-images/a%20b.png"),
    ],
)
def test_build_source_url_encodes_the_key(key, path):
    """URL syntax in a key is escaped, so the URL names that exact object."""
    assert build_source_url(BASE, key) == BASE + path


@pytest.mark.django_db
@responses.activate
def test_key_with_url_syntax_fetches_that_object(storage):
    """A "#" in a key is part of the object name, not a URL fragment."""
    make_image(str(COURSE), "vid-1", "video-images/frame#1.png")
    responses.get(
        BASE + "video-images/frame%231.png", body=PNG, content_type="image/png"
    )

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.copied == ["video-images/frame#1.png"]
    assert storage.open("video-images/frame#1.png").read() == PNG


@pytest.mark.django_db
@responses.activate
def test_renamed_save_is_removed_and_reported_missing(storage, mocker):
    """If storage saves under another name, the stray file is removed."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    responses.get(BASE + "video-images/a.png", body=PNG, content_type="image/png")
    storage.save("video-images/a_renamed.png", ContentFile(PNG))
    mocker.patch.object(storage, "save", return_value="video-images/a_renamed.png")

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.missing == ["video-images/a.png"]
    assert result.copied == []
    assert not storage.exists("video-images/a_renamed.png")


@pytest.mark.django_db
@responses.activate
def test_non_image_response_is_missing_and_not_saved(storage):
    """A 200 that isn't an image (e.g. a wrong base URL) is not stored."""
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    responses.get(
        BASE + "video-images/a.png", body="<html></html>", content_type="text/html"
    )

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.missing == ["video-images/a.png"]
    assert not storage.exists("video-images/a.png")


@pytest.mark.django_db
@responses.activate
@pytest.mark.parametrize(
    ("body", "content_type"),
    [
        pytest.param(b"PNGDATA", "image/png", id="not-an-image"),
        pytest.param(b"", "image/png", id="empty"),
        pytest.param(PNG[: len(PNG) // 2], "image/png", id="truncated-png"),
        # Image.verify() passes this one; only a full decode catches it.
        pytest.param(BMP[: len(BMP) // 2], "image/bmp", id="truncated-bmp"),
    ],
)
def test_broken_image_is_missing_and_not_saved(storage, body, content_type):
    """An image Content-Type whose body doesn't decode is not stored.

    Saving it would stick, since later runs skip keys that already exist.
    """
    make_image(str(COURSE), "vid-1", "video-images/a.png")
    responses.get(BASE + "video-images/a.png", body=body, content_type=content_type)

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.missing == ["video-images/a.png"]
    assert not storage.exists("video-images/a.png")


@pytest.mark.django_db
@responses.activate
def test_storage_error_on_one_key_does_not_stop_the_rest(storage, mocker):
    """A storage error (e.g. a traversal key from OLX) only affects that key."""
    make_image(str(COURSE), "vid-1", "video-images/../../x.png")
    make_image(str(COURSE), "vid-2", "video-images/ok.png")
    responses.get(BASE + "video-images/ok.png", body=PNG, content_type="image/png")
    real_exists = storage.exists

    def exists(name):
        if ".." in name:
            raise SuspiciousFileOperation(name)
        return real_exists(name)

    mocker.patch.object(storage, "exists", side_effect=exists)

    result = copy_course_thumbnails(COURSE, BASE)

    assert result.missing == ["video-images/../../x.png"]
    assert result.copied == ["video-images/ok.png"]
