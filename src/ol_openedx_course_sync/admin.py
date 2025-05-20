"""
Django admin for ol-openedx-course-sync plugin
"""

from django import forms
from django.contrib import admin
from ol_openedx_course_sync.models import CourseRunSyncMap, CourseSyncOrganization
from organizations.models import Organization


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
    form = CourseSyncOrganizationForm
    list_display = ("organization", "is_active")


class CourseRunSyncMapAdmin(admin.ModelAdmin):
    list_display = ("source_course", "target_course", "is_active")
    search_fields = ("source_course", "target_course")
    list_filter = ("is_active",)


admin.site.register(CourseSyncOrganization, CourseSyncOrganizationAdmin)
admin.site.register(CourseRunSyncMap, CourseRunSyncMapAdmin)
