"""
Django admin pages for git-auto-export plugin
"""

from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.db.models import Q
from opaque_keys.edx.locator import LibraryLocator, LibraryLocatorV2

from ol_openedx_git_auto_export.constants import (
    LIBRARY_V1_PREFIX,
    LIBRARY_V2_PREFIX,
    ContentType,
)
from ol_openedx_git_auto_export.models import ContentGitRepository


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
    )
    search_fields = ("content_key", "git_url")
    list_filter = ("is_export_enabled", ContentTypeFilter)
    list_per_page = 50

    @admin.display(description="Content Type")
    def content_type_display(self, obj):
        """Display whether the content is a course or library."""
        if isinstance(obj.content_key, (LibraryLocator, LibraryLocatorV2)):
            return ContentType.LIBRARY.display_name
        return ContentType.COURSE.display_name

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """
        Disable delete permission for ContentGitRepository objects.

        Deleting a ContentGitRepository could lead to orphaned repositories
        on GitHub and loss of export functionality.

        To stop exporting content, set `is_export_enabled` to False
        """
        return False
