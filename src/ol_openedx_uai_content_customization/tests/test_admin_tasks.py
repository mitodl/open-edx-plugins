"""Tests for admin-triggered UAI generation jobs."""

from unittest import mock

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import RequestFactory
from ol_openedx_uai_content_customization.admin import UAICourseGenerationJobAdmin
from ol_openedx_uai_content_customization.models import UAICourseGenerationJob
from ol_openedx_uai_content_customization.tasks import run_uai_course_generation_job

pytestmark = pytest.mark.django_db


@pytest.fixture(name="admin_user")
def admin_user_fixture():
    """Create a superuser for admin action tests."""
    User = get_user_model()
    return User.objects.create_superuser(
        username="uai_admin",
        email="uai_admin@example.com",
        password="x",  # noqa: S106
    )


@pytest.fixture(name="generation_job")
def generation_job_fixture(admin_user):
    """Create a minimal UAI generation job with uploaded CSV files."""
    customized_csv = SimpleUploadedFile(
        "customized.csv",
        b"course_key,industry,duration,video_file_name,video_title,module_name\n",
    )
    video_assets_csv = SimpleUploadedFile(
        "assets.csv",
        b"name,video_id\n",
    )
    return UAICourseGenerationJob.objects.create(
        customized_csv=customized_csv,
        video_assets_csv=video_assets_csv,
        created_by=admin_user,
    )


def test_run_uai_course_generation_job_success(generation_job):
    """Task marks job as succeeded when command execution succeeds."""

    def _successful_call(**kwargs):
        kwargs["stdout"].write("Done. Created: 1  Skipped: 0")

    with mock.patch(
        "ol_openedx_uai_content_customization.tasks.call_command",
        side_effect=_successful_call,
    ):
        run_uai_course_generation_job(generation_job.id)

    generation_job.refresh_from_db()
    assert generation_job.status == UAICourseGenerationJob.Status.SUCCEEDED
    assert "Created: 1" in generation_job.output
    assert generation_job.started_at is not None
    assert generation_job.completed_at is not None


def test_run_uai_course_generation_job_failure(generation_job):
    """Task marks job as failed and stores failure output on command error."""
    error_msg = "boom"

    def _failing_call(**kwargs):
        kwargs["stdout"].write("partial log")
        raise RuntimeError(error_msg)

    with mock.patch(
        "ol_openedx_uai_content_customization.tasks.call_command",
        side_effect=_failing_call,
    ):
        run_uai_course_generation_job(generation_job.id)

    generation_job.refresh_from_db()
    assert generation_job.status == UAICourseGenerationJob.Status.FAILED
    assert "partial log" in generation_job.output
    assert "ERROR: boom" in generation_job.output


def test_admin_action_queues_job(generation_job, admin_user):
    """Admin action enqueues async task and records Celery task id."""
    model_admin = UAICourseGenerationJobAdmin(UAICourseGenerationJob, AdminSite())
    request = RequestFactory().post("/admin/")
    request.user = admin_user

    with (
        mock.patch(
            "ol_openedx_uai_content_customization.admin.run_uai_course_generation_job.delay"
        ) as mock_delay,
        mock.patch.object(model_admin, "message_user"),
    ):
        mock_delay.return_value.id = "task-123"
        model_admin.run_selected_jobs(
            request,
            UAICourseGenerationJob.objects.all(),
        )

    generation_job.refresh_from_db()
    assert generation_job.task_id == "task-123"
    assert generation_job.status == UAICourseGenerationJob.Status.PENDING


def test_generation_job_rejects_non_csv_upload(admin_user):
    """Model validation rejects non-CSV file extensions."""
    bad_customized = SimpleUploadedFile("customized.txt", b"x")
    assets_csv = SimpleUploadedFile("assets.csv", b"name,video_id\n")

    with pytest.raises(ValidationError):
        UAICourseGenerationJob.objects.create(
            customized_csv=bad_customized,
            video_assets_csv=assets_csv,
            created_by=admin_user,
        )
