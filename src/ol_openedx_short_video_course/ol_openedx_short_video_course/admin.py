"""Django admin for the ol-openedx-short-video-course plugin."""

from django.contrib import admin

from ol_openedx_short_video_course.models import (
    ShortCourseCreationJob,
    ShortCourseVariant,
)


class ShortCourseVariantInline(admin.TabularInline):
    """Inline view of created courses within a creation job."""

    model = ShortCourseVariant
    extra = 0
    readonly_fields = (
        "course_name",
        "dest_course_key",
        "status",
        "error_log",
        "sections_created",
        "subsections_created",
        "units_created",
        "created_at",
        "updated_at",
    )
    can_delete = False

    def has_add_permission(self, _request, _obj=None):
        """Disallow inline creation from admin."""
        return False


@admin.register(ShortCourseCreationJob)
class ShortCourseCreationJobAdmin(admin.ModelAdmin):
    """Read-only admin view of short course creation jobs."""

    list_display = ("pk", "csv_path", "run_by_email", "status", "created_at")
    list_filter = ("status",)
    readonly_fields = (
        "csv_path",
        "run_by_email",
        "status",
        "error_summary",
        "created_at",
        "updated_at",
    )
    inlines = [ShortCourseVariantInline]

    def has_add_permission(self, _request):
        """Disallow creating job rows from admin."""
        return False

    def has_change_permission(self, _request, _obj=None):
        """Disallow editing job rows from admin."""
        return False


@admin.register(ShortCourseVariant)
class ShortCourseVariantAdmin(admin.ModelAdmin):
    """Read-only admin view of individual created courses."""

    list_display = (
        "pk",
        "batch",
        "course_name",
        "dest_course_key",
        "status",
        "sections_created",
        "subsections_created",
        "units_created",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("course_name", "dest_course_key")
    readonly_fields = (
        "batch",
        "course_name",
        "dest_course_key",
        "status",
        "error_log",
        "sections_created",
        "subsections_created",
        "units_created",
        "created_at",
        "updated_at",
    )

    def has_add_permission(self, _request):
        """Disallow creating variant rows from admin."""
        return False

    def has_change_permission(self, _request, _obj=None):
        """Disallow editing variant rows from admin."""
        return False
