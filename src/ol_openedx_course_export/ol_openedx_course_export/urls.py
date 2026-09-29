"""
Course export API endpoint urls.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_course_export.views import CourseContentVersionsView, CourseExportView

urlpatterns = [
    # Ahead of the catch-all below, which would otherwise route it to the export.
    re_path(
        r"^versions/$",
        CourseContentVersionsView.as_view(),
        name="course_content_versions",
    ),
    re_path(
        rf"^{settings.COURSE_ID_PATTERN}/$",
        CourseExportView.as_view(),
        name="course_export_status",
    ),
    re_path(r"^", CourseExportView.as_view(), name="course_export"),
]
