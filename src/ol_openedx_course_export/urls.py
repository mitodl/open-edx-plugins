"""
Course export API endpoint urls.
"""

from django.urls import re_path

from ol_openedx_course_export.views import CourseExportView

urlpatterns = [
    re_path(r"^", CourseExportView.as_view(), name="course_export"),
]
