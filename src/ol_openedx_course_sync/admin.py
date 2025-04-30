"""
Django admin for ol-openedx-course-sync plugin
"""

from django.contrib import admin
from ol_openedx_course_sync.models import CourseSyncMap, CourseSyncParentOrg


class CourseSyncParentOrgAdmin(admin.ModelAdmin):
    list_display = ("organization",)


class CourseSyncMapAdmin(admin.ModelAdmin):
    list_display = ("source_course", "target_courses")
    search_fields = ("source_course", "target_courses")


admin.site.register(CourseSyncParentOrg, CourseSyncParentOrgAdmin)
admin.site.register(CourseSyncMap, CourseSyncMapAdmin)
