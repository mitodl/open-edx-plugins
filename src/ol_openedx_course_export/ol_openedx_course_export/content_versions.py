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
The one read of course structure, to find a course's videos, is a single
aggregation per batch, cached per published version.
"""

from datetime import UTC, datetime

from bson import ObjectId
from common.djangoapps.split_modulestore_django.models import (
    SplitModulestoreCourseIndex,
)
from django.core.cache import cache
from django.db.models import Count, Max
from edxval.models import VideoTranscript
from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey
from opaque_keys.edx.locator import CourseLocator
from pymongo import DESCENDING
from xmodule.contentstore.django import contentstore
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.django import modulestore

ONE_WEEK_SECONDS = 7 * 24 * 60 * 60
VIDEO_IDS_CACHE_KEY = "ol_openedx_course_export.video_ids.{}"
VIDEO_IDS_PER_QUERY = 5000


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


def _video_ids(published_versions: set[str]) -> dict[str, list[str]]:
    """List the VAL video ids the video blocks of each published structure name.

    A structure never changes once written, so its video ids are cached under its
    id and Mongo is only asked about versions published since the last poll. The
    aggregation filters to video blocks on the server, so no course structure
    crosses the wire.
    """
    keys = {
        VIDEO_IDS_CACHE_KEY.format(version): version for version in published_versions
    }
    video_ids = {keys[key]: ids for key, ids in cache.get_many(keys).items()}
    uncached = published_versions - video_ids.keys()
    if uncached:
        split = modulestore()._get_modulestore_by_type(  # noqa: SLF001
            ModuleStoreEnum.Type.split
        )
        video_blocks = {
            "$filter": {
                "input": "$blocks",
                "cond": {"$eq": ["$$this.block_type", "video"]},
            }
        }
        structures = split.db_connection.structures.aggregate(
            [
                {"$match": {"_id": {"$in": [ObjectId(v) for v in uncached]}}},
                {
                    "$project": {
                        "video_ids": {
                            "$map": {
                                "input": video_blocks,
                                "in": "$$this.fields.edx_video_id",
                            }
                        }
                    }
                },
            ]
        )
        fresh = {
            str(structure["_id"]): sorted(
                {
                    video_id.strip()
                    for video_id in structure["video_ids"]
                    if video_id and video_id.strip()
                }
            )
            for structure in structures
        }
        cache.set_many(
            {
                VIDEO_IDS_CACHE_KEY.format(version): ids
                for version, ids in fresh.items()
            },
            ONE_WEEK_SECONDS,
        )
        video_ids.update(fresh)
    return video_ids


def _transcripts(published: dict[str, str]) -> dict[str, dict]:
    """Count each course's VAL transcripts and find the latest change to any.

    Replacing a transcript updates its row, which moves ``modified``; removing
    one moves the count. The transcripts are those of the videos the course's
    published video blocks name, which is how an export finds them. VAL's own
    course-to-video link is not used: a video created by uploading a transcript
    in the Studio video editor (an "external" video) is linked to no course.

    A video that only an unpublished block names is not counted until the block
    is published, though an export writes draft blocks too. The published
    version has the same blind spot for all draft content.

    Ids are compared in lower case, because an export looks a video up with an
    equality MySQL's default collation answers without regard to case.

    ``published`` maps course id to published version. One Mongo aggregation
    for the whole batch, and one query per ``VIDEO_IDS_PER_QUERY`` videos.
    """
    video_ids = _video_ids({version for version in published.values() if version})
    wanted = sorted({video_id for ids in video_ids.values() for video_id in ids})
    by_video = {}
    for start in range(0, len(wanted), VIDEO_IDS_PER_QUERY):
        rows = (
            VideoTranscript.objects.filter(
                video__edx_video_id__in=wanted[start : start + VIDEO_IDS_PER_QUERY]
            )
            .values("video__edx_video_id")
            .annotate(transcript_count=Count("id"), latest_modified=Max("modified"))
        )
        by_video.update({row["video__edx_video_id"].lower(): row for row in rows})
    transcripts = {}
    for course_id, version in published.items():
        course_rows = [
            by_video[video_id]
            for video_id in {v.lower() for v in video_ids.get(version, [])}
            if video_id in by_video
        ]
        transcripts[course_id] = {
            "count": sum(row["transcript_count"] for row in course_rows),
            "latest_modified": _isoformat(
                max((row["latest_modified"] for row in course_rows), default=None)
            ),
        }
    return transcripts


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

    transcripts = _transcripts(
        {course_id: published[key] for course_id, key in found.items()}
    )
    versions = {
        course_id: {
            "published_version": published[key],
            "static_assets": _static_assets(key),
            "transcripts": transcripts[course_id],
        }
        for course_id, key in found.items()
    }
    absent = set(missing)
    return versions, [
        course_id for course_id in dict.fromkeys(course_ids) if course_id in absent
    ]
