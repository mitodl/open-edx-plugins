"""Copy a course's video thumbnails from another instance's public storage."""

import logging
from dataclasses import dataclass, field
from http import HTTPStatus
from io import BytesIO
from urllib.parse import quote

import requests
from django.core.files.base import ContentFile
from edxval.models import VideoImage
from edxval.utils import get_video_image_storage
from opaque_keys.edx.keys import CourseKey
from PIL import Image

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class CopyResult:
    """Thumbnail keys grouped by what happened to them, each list sorted."""

    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def build_source_url(base_url: str, key: str) -> str:
    """
    Join the source storage base URL and a thumbnail key with one slash.

    The key is percent-encoded (keeping "/"), so "#", "?" or "%" in it stay
    part of the object name instead of being read as URL syntax.
    """
    return f"{base_url.rstrip('/')}/{quote(key.lstrip('/'), safe='/')}"


def _course_image_keys(course_key: CourseKey) -> list[str]:
    """Return the distinct, non-empty thumbnail keys of a course, sorted."""
    names = VideoImage.objects.filter(
        course_video__course_id=str(course_key)
    ).values_list("image", flat=True)
    return sorted({name for name in names if name})


def _is_complete_image(content: bytes) -> bool:
    """Return whether ``content`` decodes fully as an image."""
    try:
        with Image.open(BytesIO(content)) as image:
            # load() decodes every pixel; verify() passes e.g. a truncated BMP.
            image.load()
    except (OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return False
    return True


def _download(url: str) -> bytes | None:
    """Return the file at ``url``, or None if it can't be fetched."""
    try:
        response = requests.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    except requests.RequestException:
        log.warning("Could not fetch video thumbnail %s", url, exc_info=True)
        return None
    if response.status_code != HTTPStatus.OK:
        log.warning(
            "Could not fetch video thumbnail %s: HTTP %s", url, response.status_code
        )
        return None
    content_type = response.headers.get("Content-Type", "")
    if not content_type.startswith("image/"):
        # Usually a wrong base URL. Saving it would stick: existing keys are skipped.
        log.warning(
            "Not saving video thumbnail %s: Content-Type is %r", url, content_type
        )
        return None
    if not _is_complete_image(response.content):
        # A truncated or corrupt body would stick the same way.
        log.warning("Not saving video thumbnail %s: not a complete image", url)
        return None
    return response.content


def _copy_one(storage, key: str, source_base_url: str, *, dry_run: bool) -> str:
    """Copy one thumbnail; return "copied", "skipped" or "missing"."""
    if storage.exists(key):
        return "skipped"
    if dry_run:
        return "copied"
    content = _download(build_source_url(source_base_url, key))
    if content is None:
        return "missing"
    saved = storage.save(key, ContentFile(content))
    if saved != key:
        # Storage renamed the file, so the VideoImage row wouldn't find it.
        log.error("Video thumbnail %s was saved as %s; removing it", key, saved)
        storage.delete(saved)
        return "missing"
    return "copied"


def copy_course_thumbnails(
    course_key: CourseKey, source_base_url: str, *, dry_run: bool = False
) -> CopyResult:
    """
    Copy the course's thumbnails missing from local storage, keeping their keys.

    Course import leaves each ``VideoImage`` pointing at the key the image had
    on the source instance. Keys already present locally are never touched.
    A key that fails (download or storage error) is reported as missing and
    doesn't stop the others.
    """
    storage = get_video_image_storage()
    result = CopyResult()
    for key in _course_image_keys(course_key):
        try:
            outcome = _copy_one(storage, key, source_base_url, dry_run=dry_run)
        except Exception:
            # e.g. SuspiciousFileOperation for a "../" key from course OLX, or S3 errors
            log.exception("Could not copy video thumbnail %s", key)
            outcome = "missing"
        getattr(result, outcome).append(key)
    return result
