"""Copy a course's video thumbnails from another instance's public storage."""

import logging
from dataclasses import dataclass, field
from http import HTTPStatus

import requests
from django.core.files.base import ContentFile
from edxval.models import VideoImage
from edxval.utils import get_video_image_storage
from opaque_keys.edx.keys import CourseKey

log = logging.getLogger(__name__)

REQUEST_TIMEOUT_SECONDS = 30


@dataclass
class CopyResult:
    """Thumbnail keys grouped by what happened to them, each list sorted."""

    copied: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)


def build_source_url(base_url: str, key: str) -> str:
    """Join the source storage base URL and a thumbnail key with one slash."""
    return f"{base_url.rstrip('/')}/{key.lstrip('/')}"


def _course_image_keys(course_key: CourseKey) -> list[str]:
    """Return the distinct, non-empty thumbnail keys of a course, sorted."""
    names = VideoImage.objects.filter(
        course_video__course_id=str(course_key)
    ).values_list("image", flat=True)
    return sorted({name for name in names if name})


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
    return response.content


def copy_course_thumbnails(
    course_key: CourseKey, source_base_url: str, *, dry_run: bool = False
) -> CopyResult:
    """
    Copy the course's thumbnails missing from local storage, keeping their keys.

    Course import leaves each ``VideoImage`` pointing at the key the image had
    on the source instance. Keys already present locally are never touched.
    """
    storage = get_video_image_storage()
    result = CopyResult()
    for key in _course_image_keys(course_key):
        if storage.exists(key):
            result.skipped.append(key)
            continue
        if dry_run:
            result.copied.append(key)
            continue
        content = _download(build_source_url(source_base_url, key))
        if content is None:
            result.missing.append(key)
            continue
        saved = storage.save(key, ContentFile(content))
        if saved != key:
            # Storage renamed the file, so the VideoImage row wouldn't find it.
            log.error("Video thumbnail %s was saved as %s; removing it", key, saved)
            storage.delete(saved)
            result.missing.append(key)
            continue
        result.copied.append(key)
    return result
