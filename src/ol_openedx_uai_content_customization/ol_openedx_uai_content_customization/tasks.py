"""Asynchronous tasks for UAI course generation."""

import logging
from io import StringIO
from pathlib import Path

from celery import shared_task
from django.core.exceptions import ObjectDoesNotExist
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from ol_openedx_uai_content_customization.models import UAICourseGenerationJob

log = logging.getLogger(__name__)


@shared_task
def run_uai_course_generation_job(job_id):
    """Execute ``generate_uai_courses`` for a job and persist the outcome."""
    try:
        job = UAICourseGenerationJob.objects.get(id=job_id)
    except ObjectDoesNotExist:
        log.exception("UAI generation job %s not found", job_id)
        return

    if job.status == UAICourseGenerationJob.Status.RUNNING:
        log.warning("UAI generation job %s is already running", job_id)
        return

    job.status = UAICourseGenerationJob.Status.RUNNING
    job.started_at = timezone.now()
    job.completed_at = None
    job.output = ""
    job.save(
        update_fields=["status", "started_at", "completed_at", "output", "updated_at"]
    )

    customized_csv_path = _safe_local_path(job.customized_csv)
    video_assets_csv_path = _safe_local_path(job.video_assets_csv)
    missing_paths = [
        path
        for path in (customized_csv_path, video_assets_csv_path)
        if not path or not Path(path).exists()
    ]

    if missing_paths:
        _mark_failed(
            job,
            "CSV file(s) are unavailable on disk. Re-upload files and retry.",
        )
        return

    output_buffer = StringIO()

    try:
        call_command(
            "generate_uai_courses",
            customized_csv=customized_csv_path,
            video_assets_csv=video_assets_csv_path,
            username=job.username,
            dry_run=job.dry_run,
            stdout=output_buffer,
        )
    except CommandError as exc:
        _mark_failed(job, _format_output(output_buffer.getvalue(), str(exc)))
        log.exception("UAI generation job %s failed", job_id)
        return
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        _mark_failed(job, _format_output(output_buffer.getvalue(), str(exc)))
        log.exception("UAI generation job %s failed", job_id)
        return

    job.status = UAICourseGenerationJob.Status.SUCCEEDED
    job.completed_at = timezone.now()
    job.output = output_buffer.getvalue().strip()
    job.save(update_fields=["status", "completed_at", "output", "updated_at"])


def _safe_local_path(field_file):
    """Return local path for uploaded files when available."""
    try:
        return field_file.path
    except (NotImplementedError, ValueError, AttributeError):
        return ""


def _mark_failed(job, output):
    """Persist a failed job state and command output."""
    job.status = UAICourseGenerationJob.Status.FAILED
    job.completed_at = timezone.now()
    job.output = output
    job.save(update_fields=["status", "completed_at", "output", "updated_at"])


def _format_output(stdout_text, error_text):
    """Build readable failure output combining command logs and exception text."""
    if stdout_text.strip():
        return f"{stdout_text.strip()}\n\nERROR: {error_text}"
    return f"ERROR: {error_text}"
