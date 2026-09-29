"""
Report what a course export would reflect, without exporting it.

A course's published version only moves when content in the modulestore is
published. Two things a Studio export also carries never move it: files uploaded
to the course's Files page (the contentstore), and video transcripts uploaded
through VAL. A caller that re-exports a course whenever the published version
changes therefore misses both, and its copy drifts from the live course. This
module reports all three, read straight from where they are stored, so a caller
can tell when an export has gone stale.

Everything here is a lookup against an index or an aggregate, never a walk of the
course tree, because it is meant to be polled for every course on an instance.
"""

from datetime import UTC, datetime

from common.djangoapps.split_modulestore_django.models import (
    SplitModulestoreCourseIndex,
)
from django.db.models import Count, Max
from edxval.models import CourseVideo
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import CourseLocator
from pymongo import DESCENDING
from xmodule.contentstore.django import contentstore


def _isoformat(value: datetime | None) -> str | None:
    """Render a timestamp as ISO 8601 UTC.

    pymongo hands back naive datetimes that are already UTC, while Django hands
    back aware ones, so both are pinned to UTC before rendering.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _static_assets(course_key: CourseKey) -> dict:
    """Count a course's uploaded files and name the most recently uploaded one.

    Uploading or replacing a file moves the newest upload; deleting one moves the
    count. Toggling an asset's lock moves neither, which is a known blind spot.
    """
    assets, count = contentstore().get_all_content_for_course(
        course_key, maxresults=1, sort=[("uploadDate", DESCENDING)]
    )
    newest = assets[0] if assets else None
    return {
        "count": count,
        "latest_upload": _isoformat(newest["uploadDate"]) if newest else None,
        "latest_asset": str(newest["asset_key"]) if newest else None,
    }


def _transcripts(course_ids: list[str]) -> dict[str, dict]:
    """Count each course's VAL transcripts and find the latest change to any.

    Replacing a transcript updates its row, which moves ``modified``; removing
    one moves the count. One query for the whole batch.
    """
    rows = (
        CourseVideo.objects.filter(course_id__in=course_ids)
        .values("course_id")
        .annotate(
            transcript_count=Count("video__video_transcripts"),
            latest_modified=Max("video__video_transcripts__modified"),
        )
    )
    return {
        row["course_id"]: {
            "count": row["transcript_count"],
            "latest_modified": _isoformat(row["latest_modified"]),
        }
        for row in rows
    }


def course_content_versions(course_ids: list[str]) -> tuple[dict[str, dict], list[str]]:
    """Report the published version, files and transcripts of each course.

    Returns the per-course facts, and the requested ids that name no course on
    this instance, in request order. That includes ids that do not parse as
    course keys, and library keys: ``library-v1:`` ids parse as course keys and
    have rows in the course index, but a library is not a course.
    """
    keys: dict[str, CourseKey] = {}
    missing: list[str] = []
    for course_id in dict.fromkeys(course_ids):
        try:
            key = CourseKey.from_string(course_id)
        except InvalidKeyError:
            missing.append(course_id)
            continue
        if isinstance(key, CourseLocator):
            keys[course_id] = key
        else:
            missing.append(course_id)

    published = dict(
        SplitModulestoreCourseIndex.objects.filter(
            course_id__in=list(keys.values())
        ).values_list("course_id", "published_version")
    )
    found = {course_id: key for course_id, key in keys.items() if key in published}
    missing.extend(course_id for course_id in keys if course_id not in found)

    transcripts = _transcripts(list(found))
    no_transcripts = {"count": 0, "latest_modified": None}
    versions = {
        course_id: {
            "published_version": published[key],
            "static_assets": _static_assets(key),
            "transcripts": transcripts.get(course_id, no_transcripts),
        }
        for course_id, key in found.items()
    }
    absent = set(missing)
    return versions, [
        course_id for course_id in dict.fromkeys(course_ids) if course_id in absent
    ]
