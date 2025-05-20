"""
Django admin for ol-openedx-course-sync plugin
"""

from django.contrib import admin
from ol_openedx_course_sync.models import CourseSyncMap, CourseSyncOrganization


class CourseSyncOrganizationAdmin(admin.ModelAdmin):
    list_display = ("organization", "is_active")


class CourseSyncMapAdmin(admin.ModelAdmin):
    list_display = ("source_course", "target_course", "is_active")
    search_fields = ("source_course", "target_course")
    list_filter = ("is_active",)


admin.site.register(CourseSyncOrganization, CourseSyncOrganizationAdmin)
admin.site.register(CourseSyncMap, CourseSyncMapAdmin)
