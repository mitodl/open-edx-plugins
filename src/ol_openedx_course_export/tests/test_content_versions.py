"""
Tests for the course content versions endpoint.
"""

from http import HTTPStatus

from common.djangoapps.split_modulestore_django.models import (
    SplitModulestoreCourseIndex,
)
from common.djangoapps.student.tests.factories import UserFactory
from django.core.files.base import ContentFile
from edxval.api import create_or_update_video_transcript, create_video
from freezegun import freeze_time
from ol_openedx_course_export.views import MAX_COURSES_PER_VERSIONS_REQUEST
from rest_framework.test import APIClient
from xmodule.contentstore.content import StaticContent
from xmodule.contentstore.django import contentstore
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import BlockFactory, CourseFactory

VERSIONS_URL = "/api/courses/v0/export/versions/"


class CourseContentVersionsViewTests(ModuleStoreTestCase):
    """Tests for POST /api/courses/v0/export/versions/."""

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create(default_store=ModuleStoreEnum.Type.split)
        self.course_id = str(self.course.id)
        self.client = APIClient()
        self.client.force_authenticate(UserFactory.create(is_staff=True))

    def _versions(self, *course_ids):
        response = self.client.post(
            VERSIONS_URL, {"courses": list(course_ids)}, format="json"
        )
        assert response.status_code == HTTPStatus.OK, response.content
        return response.json()

    def _upload(self, name, data=b"data"):
        asset_key = self.course.id.make_asset_key("asset", name)
        contentstore().save(StaticContent(asset_key, name, "text/plain", data))
        return asset_key

    def _add_transcript(self, video_id, language, data):
        create_or_update_video_transcript(
            video_id,
            language,
            metadata={"provider": "Custom", "file_format": "srt"},
            file_data=ContentFile(data),
        )

    def test_reports_the_course_index_published_version(self):
        """The version is the one the course index holds, and moves on publish."""
        before = self._versions(self.course_id)["versions"][self.course_id]
        assert before["published_version"] == (
            SplitModulestoreCourseIndex.objects.get(
                course_id=self.course.id
            ).published_version
        )

        BlockFactory.create(
            parent_location=self.course.location,
            category="chapter",
            publish_item=True,
            user_id=self.user.id,
        )

        after = self._versions(self.course_id)["versions"][self.course_id]
        assert after["published_version"] != before["published_version"]

    def test_a_course_with_no_files_or_transcripts(self):
        """An empty course reports zero counts rather than leaving keys out."""
        version = self._versions(self.course_id)["versions"][self.course_id]

        assert version["static_assets"] == {
            "count": 0,
            "latest_upload": None,
            "latest_asset": None,
        }
        assert version["transcripts"] == {"count": 0, "latest_modified": None}

    def test_uploading_a_file_moves_the_static_assets_facts(self):
        """A new upload is counted and becomes the newest asset."""
        with freeze_time("2026-09-01T12:00:00Z"):
            self._upload("syllabus.pdf")
        with freeze_time("2026-09-02T12:00:00Z"):
            handout = self._upload("handout.pdf")

        assets = self._versions(self.course_id)["versions"][self.course_id][
            "static_assets"
        ]

        assert assets["count"] == 2  # noqa: PLR2004
        assert assets["latest_asset"] == str(handout)
        assert assets["latest_upload"].startswith("2026-09-02T12:00:00")

    def test_transcripts_are_counted_and_replacements_move_latest_modified(self):
        """Adding counts a transcript; replacing one moves latest_modified."""
        create_video(
            {
                "edx_video_id": "video-1",
                "status": "file_complete",
                "client_video_id": "Lecture 1",
                "duration": 60,
                "encoded_videos": [],
                "courses": [self.course_id],
            }
        )
        with freeze_time("2026-09-01T12:00:00Z"):
            self._add_transcript(
                "video-1", "en", b"1\n00:00:00,000 --> 00:00:01,000\nhi\n"
            )
            self._add_transcript(
                "video-1", "fr", b"1\n00:00:00,000 --> 00:00:01,000\nsalut\n"
            )
        before = self._versions(self.course_id)["versions"][self.course_id]
        with freeze_time("2026-09-05T12:00:00Z"):
            self._add_transcript(
                "video-1", "en", b"1\n00:00:00,000 --> 00:00:01,000\nhello\n"
            )
        after = self._versions(self.course_id)["versions"][self.course_id]

        assert before["transcripts"]["count"] == 2  # noqa: PLR2004
        assert after["transcripts"]["count"] == 2  # noqa: PLR2004
        assert after["transcripts"]["latest_modified"].startswith("2026-09-05T12:00:00")

    def test_unknown_and_unparseable_ids_are_missing_not_fatal(self):
        """Ids with no course are listed as missing; the rest are still reported."""
        unknown = "course-v1:edX+Nope+2026"
        unparseable = "not a course key"

        body = self._versions(unknown, self.course_id, unparseable)

        assert list(body["versions"]) == [self.course_id]
        assert body["missing"] == [unknown, unparseable]

    def test_rejects_an_empty_or_oversized_batch(self):
        """A request must name between one and the maximum number of courses."""
        for courses in ([], [self.course_id] * (MAX_COURSES_PER_VERSIONS_REQUEST + 1)):
            response = self.client.post(
                VERSIONS_URL, {"courses": courses}, format="json"
            )
            assert response.status_code == HTTPStatus.BAD_REQUEST

    def test_forbidden_for_non_staff(self):
        """Only platform staff may read content versions."""
        client = APIClient()
        client.force_authenticate(UserFactory.create())

        response = client.post(
            VERSIONS_URL, {"courses": [self.course_id]}, format="json"
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
