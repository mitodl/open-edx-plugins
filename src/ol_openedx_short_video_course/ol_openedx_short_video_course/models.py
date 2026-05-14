"""Models for the ol-openedx-short-video-course plugin."""

from django.db import models
from opaque_keys.edx.django.models import CourseKeyField


class ShortCourseCreationJob(models.Model):
    """Audit record for one execution of the generate_custom_courses command."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_PARTIAL = "partial"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
        (STATUS_PARTIAL, "Partial"),
    ]

    csv_path = models.CharField(max_length=1024)
    run_by_email = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    error_summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata for short course creation jobs."""

        app_label = "ol_openedx_short_video_course"
        verbose_name = "Short Course Creation Job"
        verbose_name_plural = "Short Course Creation Jobs"

    def __str__(self):
        """Return a compact human-readable description of this job."""

        return f"ShortCourseCreationJob #{self.pk} ({self.status})"


class ShortCourseVariant(models.Model):
    """Audit record for one (source, type, industry) variant within a batch."""

    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_RUNNING, "Running"),
        (STATUS_SUCCESS, "Success"),
        (STATUS_FAILED, "Failed"),
    ]

    batch = models.ForeignKey(
        ShortCourseCreationJob, on_delete=models.CASCADE, related_name="variants"
    )
    source_course_key = CourseKeyField(max_length=255)
    dest_course_key = CourseKeyField(max_length=255, null=True, blank=True)
    type_code = models.CharField(max_length=50)
    industry_code = models.CharField(max_length=50)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    error_log = models.TextField(blank=True, default="")
    sections_kept = models.IntegerField(default=0)
    sections_removed = models.IntegerField(default=0)
    sections_updated = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Django model metadata for generated short course variants."""

        app_label = "ol_openedx_short_video_course"
        verbose_name = "Short Course Variant"
        verbose_name_plural = "Short Course Variants"

    def __str__(self):
        """Return a compact human-readable description of this variant."""

        return (
            f"ShortCourseVariant #{self.pk}: {self.source_course_key} → "
            f"{self.dest_course_key} ({self.status})"
        )
