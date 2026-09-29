"""
Course export API endpoint urls.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_course_export.views import CourseContentVersionsView, CourseExportView

urlpatterns = [
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
    # Anchored at both ends. An unanchored pattern here caught every path under
    # api/courses/v0/export/ that nothing above matched, so a POST meant for an
    # endpoint the installed release does not have (e.g. versions/ before 0.4.0)
    # queued an export of every course in its body instead of failing.
    re_path(r"^$", CourseExportView.as_view(), name="course_export"),
]
