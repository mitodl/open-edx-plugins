"""
Django admin pages for git-auto-export plugin
"""

from django.contrib import admin

from ol_openedx_git_auto_export.models import CourseGitHubRepository


@admin.register(CourseGitHubRepository)
class CourseGitHubRepositoryAdmin(admin.ModelAdmin):
    """
    Admin interface for the CourseGitHubRepository model.
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
        Disable delete permission for CourseGitHubRepository objects.
        """
        return False
