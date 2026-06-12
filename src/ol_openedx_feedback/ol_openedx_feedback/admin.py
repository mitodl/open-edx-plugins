"""Django admin for browsing feedback (staff fallback view)."""

from django.contrib import admin

from ol_openedx_feedback.models import BlockFeedback


@admin.register(BlockFeedback)
class BlockFeedbackAdmin(admin.ModelAdmin):
    """Read-only admin listing of block feedback submissions."""

    list_display = ("id", "created", "course_id", "block_type", "rating", "user_id")
    list_filter = ("rating", "block_type", "created")
    search_fields = ("course_id", "block_usage_key", "comment")
    readonly_fields = tuple(f.name for f in BlockFeedback._meta.fields)  # noqa: SLF001

    def has_add_permission(self, request):  # noqa: ARG002
        """Feedback is created via the API, never in the admin."""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Feedback rows are immutable once submitted."""
        return False
