"""
Tests for the S3 course export task.
"""

from unittest.mock import patch

from cms.djangoapps.contentstore.tests.utils import CourseTestCase
from cms.djangoapps.contentstore.utils import reverse_course_url
from django.urls import reverse
from ol_openedx_course_export.tasks import task_upload_course_s3
from rest_framework import status
from user_tasks.models import UserTaskArtifact, UserTaskStatus


@patch("ol_openedx_course_export.tasks.S3Client")
class TaskUploadCourseS3Test(CourseTestCase):
    """
    Tests for task_upload_course_s3.
    """

    def _run_s3_export(self):
        """Run the S3 export task for the test course and return its status."""
        result = task_upload_course_s3.delay(self.user.id, str(self.course.id))
        return UserTaskStatus.objects.get(task_id=result.id)

    def test_status_has_its_own_name(self, mock_s3_client):
        """
        The task's status must not use Studio's "Export of <course key>" name.
        """
        task_status = self._run_s3_export()

        assert task_status.state == UserTaskStatus.SUCCEEDED
        assert task_status.name == f"S3 export of {self.course.id}"
        assert not UserTaskArtifact.objects.filter(status=task_status).exists()
        mock_s3_client.return_value.upload_course_s3.assert_called_once()

    def test_studio_export_status_ignores_s3_export(self, mock_s3_client):  # noqa: ARG002
        """
        Studio's export status page must not pick up an S3 export as its own
        latest export (it has no Output artifact, which used to cause a 500).
        """
        self._run_s3_export()

        response = self.client.get(
            reverse_course_url("export_status_handler", self.course.id)
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"ExportStatus": 0}

    def test_status_api_finds_s3_export(self, mock_s3_client):  # noqa: ARG002
        """
        The plugin's own status API still finds the task by its new name.
        """
        task_status = self._run_s3_export()

        response = self.client.get(
            reverse("course_export_status", args=[str(self.course.id)]),
            {"task_id": task_status.task_id},
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"state": UserTaskStatus.SUCCEEDED}
