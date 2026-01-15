"""Django admin configuration for course translations plugin."""

from django.contrib import admin

from ol_openedx_course_translations.models import CourseTranslationLog


@admin.register(CourseTranslationLog)
class CourseTranslationLogAdmin(admin.ModelAdmin):
    """Admin interface for CourseTranslationLog model."""

    _common_fields = (
        "source_course_language",
        "target_course_language",
        "srt_provider_name",
        "srt_provider_model",
        "content_provider_name",
        "content_provider_model",
    )

    list_display = ("id", "source_course_id", *_common_fields, "created_at")
    list_filter = _common_fields
    readonly_fields = (
        "source_course_id",
        *_common_fields,
        "created_at",
        "command_stats",
    )
    search_fields = ("source_course_id",)
