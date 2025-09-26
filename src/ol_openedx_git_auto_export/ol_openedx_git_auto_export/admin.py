"""
Django admin pages for git-auto-export plugin
"""

from django.contrib import admin

from ol_openedx_git_auto_export.models import CourseGitRepository


@admin.register(CourseGitRepository)
class CourseGitRepositoryAdmin(admin.ModelAdmin):
    """
    Admin interface for the CourseGitRepository model.
    """

    list_display = (
        "course_key",
        "git_url",
        "is_export_enabled",
    )
    search_fields = ("course_key", "git_url")
    list_filter = ("is_export_enabled",)
    list_per_page = 50

    def has_delete_permission(self, request, obj=None):  # noqa: ARG002
        """
        Disable delete permission for CourseGitRepository objects.

        Deleting a CourseGitRepository could lead to orphaned repositories
        on GitHub and loss of course export functionality.

        To stop exporting a course, set `is_export_enabled` to False
        """
        return False
