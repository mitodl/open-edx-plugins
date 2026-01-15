"""Models for course translations plugin"""

from django.db import models
from opaque_keys.edx.django.models import CourseKeyField


class CourseTranslationLog(models.Model):
    """Log entry for course translation operations."""

    source_course_id = CourseKeyField(max_length=255, db_index=True)
    source_course_language = models.CharField(
        max_length=10,
        help_text="Source language code (e.g., 'EN')",
    )
    target_course_language = models.CharField(
        max_length=10,
        help_text="Target language code for translation (e.g., 'FR')",
    )
    srt_provider_name = models.CharField(
        max_length=100,
        help_text="LLM Provider used for SRT translation",
    )
    srt_provider_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="LLM provider model used for SRT translation",
    )
    content_provider_name = models.CharField(
        max_length=100,
        help_text="LLM Provider used for content translation",
    )
    content_provider_model = models.CharField(
        max_length=100,
        blank=True,
        help_text="LLM provider model used for content translation",
    )
    command_stats = models.TextField(
        blank=True, help_text="Logs from the translation command"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
    )
    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        """Meta options for CourseTranslationLog."""

        app_label = "ol_openedx_course_translations"

    def __str__(self):
        """Return a string representation of the translation log."""
        return (
            f"{self.source_course_id} "
            f"({self.source_course_language} → {self.target_course_language})"
        )
