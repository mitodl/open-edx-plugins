"""
Django admin pages for git-auto-export plugin
"""

from django.contrib import admin

from ol_openedx_git_auto_export.models import CourseGithubRepository


@admin.register(CourseGithubRepository)
class CourseGithubRepositoryAdmin(admin.ModelAdmin):
    """
    Admin interface for the CourseGithubRepository model.
    """

    list_display = ("course_id", "git_url")
    search_fields = ("course_id", "git_url")
    list_per_page = 50
