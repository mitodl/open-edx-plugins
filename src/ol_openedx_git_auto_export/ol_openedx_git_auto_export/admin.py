"""
Django admin pages for git-auto-export plugin
"""

from collections import Counter

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.db.models import OuterRef, Q, Subquery
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2

from ol_openedx_git_auto_export.constants import (
    LIBRARY_V1_PREFIX,
    LIBRARY_V2_PREFIX,
    ContentType,
)
from ol_openedx_git_auto_export.models import (
    ContentGitExportLog,
    ContentGitRepository,
    ExportStatus,
)
from ol_openedx_git_auto_export.utils import queue_git_exports


class ContentTypeFilter(SimpleListFilter):
    """Filter for content type (Course or Library)."""

    title = "content type"
    parameter_name = "content_type"

    def lookups(self, request, model_admin):  # noqa: ARG002
        """Return filter options."""
        return (
            (ContentType.COURSE.value, ContentType.COURSE.display_name),
            (ContentType.LIBRARY.value, ContentType.LIBRARY.display_name),
        )

    def queryset(self, request, queryset):  # noqa: ARG002
        """Filter the queryset based on the selected content type."""
        if self.value() == ContentType.COURSE.value:
            # Filter for courses (exclude libraries)
            return queryset.exclude(content_key__startswith=LIBRARY_V1_PREFIX).exclude(
                content_key__startswith=LIBRARY_V2_PREFIX
            )
        elif self.value() == ContentType.LIBRARY.value:
            # Filter for libraries
            return queryset.filter(
                Q(content_key__startswith=LIBRARY_V1_PREFIX)
                | Q(content_key__startswith=LIBRARY_V2_PREFIX)
            )
        return queryset


@admin.register(ContentGitRepository)
class ContentGitRepositoryAdmin(admin.ModelAdmin):
    """
    Admin interface for the ContentGitRepository model.

    This model supports both courses and libraries.
    """

    list_display = (
        "content_key",
        "git_url",
        "is_export_enabled",
        "content_type_display",
        "last_export_status",
        "last_export_at",
    )
    search_fields = ("content_key", "git_url")
    list_filter = ("is_export_enabled", ContentTypeFilter)
    list_per_page = 50
    actions = ("export_to_git",)

    def get_queryset(self, request):
        """Annotate each row with its newest export log entry."""
        newest = ContentGitExportLog.objects.filter(
            content_key=OuterRef("content_key")
        ).order_by("-created", "-id")
        return (
            super()
            .get_queryset(request)
            .annotate(
                last_status=Subquery(newest.values("status")[:1]),
                last_at=Subquery(newest.values("created")[:1]),
            )
        )

    @admin.display(description="Last export", ordering="last_status")
    def last_export_status(self, obj):
        """Status of the newest export log row, if any."""
        # .get: a rolled-back release may not know a newer status.
        return dict(ExportStatus.choices).get(obj.last_status, obj.last_status or "-")

    @admin.display(description="Last export at", ordering="last_at")
    def last_export_at(self, obj):
        """Time of the newest export log row, if any."""
        return obj.last_at

    @admin.display(description="Content Type")
    def content_type_display(self, obj):
        """Display whether the content is a course or library."""
        if isinstance(obj.content_key, (LibraryLocator, LibraryLocatorV2)):
            return ContentType.LIBRARY.display_name
        return ContentType.COURSE.display_name

    # Without permissions, view-only staff would get the action too.
    @admin.action(description="Export selected content to git", permissions=["change"])
    def export_to_git(self, request, queryset):
        """Queue a git export for each selected row with export enabled."""
        keys = queryset.values_list("content_key", flat=True)
        queued, skipped, errored = queue_git_exports(map(str, keys))
        self.message_user(request, f"Queued {len(queued)} git export(s).")
        if skipped:
            reasons = Counter(reason for _, reason in skipped)
            summary = ", ".join(f"{n} {reason}" for reason, n in reasons.items())
            self.message_user(
                request, f"Skipped {len(skipped)}: {summary}.", messages.WARNING
            )
        if errored:
            details = "; ".join(f"{key}: {reason}" for key, reason in errored)
            self.message_user(
                request, f"Failed to queue {len(errored)}: {details}", messages.ERROR
            )

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """
        Disable delete permission for ContentGitRepository objects.

        Deleting a ContentGitRepository could lead to orphaned repositories
        on GitHub and loss of export functionality.

        To stop exporting content, set `is_export_enabled` to False
        """
        return False


@admin.register(ContentGitExportLog)
class ContentGitExportLogAdmin(admin.ModelAdmin):
    """Read-only history of git export runs."""

    # In progress with no activity past EXPORT_TIME_LIMIT: the run was killed.
    list_display = ("content_key", "status", "user", "created", "modified", "git_url")
    list_filter = ("status", ContentTypeFilter)
    search_fields = ("content_key",)
    list_per_page = 50

    def has_add_permission(self, request):  # noqa: ARG002
        """Rows are written only by the export tasks."""
        return False

    def has_change_permission(self, request, obj=None):  # noqa: ARG002
        """Rows are an audit trail; staff can view but not edit them."""
        return False

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """Keep the full history; see README for retention."""
        return False
