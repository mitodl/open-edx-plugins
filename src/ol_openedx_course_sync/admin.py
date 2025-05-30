"""
Django admin for ol-openedx-course-sync plugin
"""

import logging

from django import forms
from django.contrib import admin
from organizations.models import Organization

from ol_openedx_course_sync.models import CourseSyncMapping, CourseSyncOrganization
from ol_openedx_course_sync.tasks import async_course_sync

log = logging.getLogger(__name__)


class CourseSyncOrganizationForm(forms.ModelForm):
    """
    Form for CourseSyncOrganization model
    """

    class Meta:
        model = CourseSyncOrganization
        fields = "__all__"  # noqa: DJ007

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        org_choices = [
            (org.name, org.name) for org in Organization.objects.filter(active=True)
        ]
        self.fields["organization"] = forms.ChoiceField(choices=org_choices)


class CourseSyncOrganizationAdmin(admin.ModelAdmin):
    """
    Admin for CourseSyncOrganization model
    """

    form = CourseSyncOrganizationForm
    list_display = ("organization", "is_active")

    def has_delete_permission(self, request, obj=None):
        """
        Disable delete permission if CourseSyncMapping is not clean
        """
        if obj and not obj.can_be_deleted():
            return False
        return super().has_delete_permission(request, obj)


class CourseSyncMappingAdmin(admin.ModelAdmin):
    """
    Admin for CourseSyncMapping model
    """

    list_display = ("source_course", "target_course", "is_active")
    search_fields = ("source_course", "target_course")
    list_filter = ("is_active",)
    actions = ("sync_course_content",)

    def get_readonly_fields(self, request, obj=None):  # noqa: ARG002
        """
        Make source_course readonly if object already exists.
        """
        if obj:
            return (*self.readonly_fields, "source_course")
        return self.readonly_fields

    @admin.action(description="Sync Course Content")
    def sync_course_content(self, request, queryset):
        """
        Sync course content for selected CourseSyncMapping(s)
        """
        for course_sync_mapping in queryset:
            log.info(
                "Initializing course content sync through admin actions from %s to %s",
                course_sync_mapping.source_course,
                course_sync_mapping.target_course,
            )
            async_course_sync.delay(
                str(course_sync_mapping.source_course),
                str(course_sync_mapping.target_course),
            )
            self.message_user(
                request,
                "Course sync started",
            )


admin.site.register(CourseSyncOrganization, CourseSyncOrganizationAdmin)
admin.site.register(CourseSyncMapping, CourseSyncMappingAdmin)
