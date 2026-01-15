from django.contrib import admin

from .models import CourseTranslationLog

"""Django admin configuration for course translations plugin."""


@admin.register(CourseTranslationLog)
class CourseTranslationLogAdmin(admin.ModelAdmin):
    """Admin interface for CourseTranslationLog model."""

    _common_fields = (
        "source_course_id",
        "source_course_language",
        "target_course_language",
        "srt_provider_name",
        "srt_provider_model",
        "content_provider_name",
        "content_provider_model",
    )

    list_display = ("id", *_common_fields, "created_at")
    list_filter = _common_fields
    readonly_fields = (*_common_fields, "created_at", "command_stats")
    search_fields = ("source_course_id",)
