"""
Course export API endpoint urls.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_course_export.views import CourseExportView

urlpatterns = [
    re_path(
        rf"^{settings.COURSE_ID_PATTERN}/$",
        CourseExportView.as_view(),
        name="course_export_status",
    ),
    re_path(r"^", CourseExportView.as_view(), name="course_export"),
]
