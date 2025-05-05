"""
Django admin pages for git-auto-export plugin
"""

from django.contrib import admin
from ol_openedx_git_auto_export.models import CourseGitRepo


class CourseGitRepoAdmin(admin.ModelAdmin):
    """
    Admin interface for the CourseGitRepo model.
    """

    list_display = ("course_id", "git_url")
    search_fields = ("course_id", "git_url")
    list_filter = ("course_id",)
    ordering = ("course_id",)
    list_per_page = 20


admin.site.register(CourseGitRepo, CourseGitRepoAdmin)
