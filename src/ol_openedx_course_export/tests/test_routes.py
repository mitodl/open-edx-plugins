"""
Tests for how the course export plugin routes requests.
"""

from http import HTTPStatus
from unittest import mock

from common.djangoapps.student.tests.factories import UserFactory
from django.test import override_settings
from rest_framework.test import APIClient
from xmodule.modulestore import ModuleStoreEnum
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

EXPORT_URL = "/api/courses/v0/export/"
UPLOAD_TASK = "ol_openedx_course_export.views.task_upload_course_s3"


@override_settings(COURSE_IMPORT_EXPORT_BUCKET="test-bucket")
class CourseExportRouteTests(ModuleStoreTestCase):
    """Only the export path itself may start an export."""

    def setUp(self):
        super().setUp()
        self.course_id = str(
            CourseFactory.create(default_store=ModuleStoreEnum.Type.split).id
        )
        self.client = APIClient()
        self.client.force_authenticate(UserFactory.create(is_staff=True))

    def test_the_export_path_still_starts_an_export(self):
        """POST /api/courses/v0/export/ queues an export of each course."""
        with mock.patch(UPLOAD_TASK) as upload:
            upload.delay.return_value.task_id = "task-1"
            response = self.client.post(
                EXPORT_URL, {"courses": [self.course_id]}, format="json"
            )

        assert response.status_code == HTTPStatus.OK, response.content
        upload.delay.assert_called_once()

    def test_an_unknown_path_under_export_is_not_an_export(self):
        """A path no endpoint serves is a 404, never an export of the body.

        An unanchored route used to catch it, so a request meant for an endpoint
        the installed release lacked exported every course it named.
        """
        with mock.patch(UPLOAD_TASK) as upload:
            response = self.client.post(
                f"{EXPORT_URL}not-an-endpoint/",
                {"courses": [self.course_id]},
                format="json",
            )

        assert response.status_code == HTTPStatus.NOT_FOUND
        upload.delay.assert_not_called()
