"""Models for ol-openedx-uai-content-customization plugin."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class UAICourseGenerationJob(models.Model):
    """Admin-managed job to run ``generate_uai_courses`` asynchronously."""

    objects = models.Manager()

    class Status(models.TextChoices):
        """Allowed execution states for a generation job."""

        PENDING = "pending", "Pending"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"

    customized_csv = models.FileField(
        upload_to="ol_openedx_uai_content_customization/jobs/",
        help_text="Customized video metadata CSV.",
    )
    video_assets_csv = models.FileField(
        upload_to="ol_openedx_uai_content_customization/jobs/",
        help_text="Open edX video asset CSV.",
    )
    username = models.CharField(
        max_length=150,
        default="studio_worker",
        help_text="Platform username used to create/publish courses.",
    )
    dry_run = models.BooleanField(
        default=False,
        help_text="When enabled, validate and report actions without writing data.",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    output = models.TextField(
        blank=True,
        help_text="Captured command output and failures.",
    )
    task_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Celery task ID for tracking asynchronous execution.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="uai_course_generation_jobs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Meta options for UAICourseGenerationJob."""

        app_label = "ol_openedx_uai_content_customization"
        ordering = ("-created_at",)

    def __str__(self):
        """Return concise job identification for admin listings."""
        return f"UAI Generation Job #{self.pk} ({self.status})"

    def save(self, *args, **kwargs):
        """Persist only validated job records."""
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        """Validate uploaded files are CSVs."""
        super().clean()
        errors = {}

        if self.customized_csv and not self.customized_csv.name.lower().endswith(
            ".csv"
        ):
            errors["customized_csv"] = "File must have a .csv extension."

        if self.video_assets_csv and not self.video_assets_csv.name.lower().endswith(
            ".csv"
        ):
            errors["video_assets_csv"] = "File must have a .csv extension."

        if errors:
            raise ValidationError(errors)
