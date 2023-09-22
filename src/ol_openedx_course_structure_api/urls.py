"""
Course structure endpoint urls.
"""

from django.conf import settings
from django.urls import re_path
from ol_openedx_course_structure_api.views import CourseStructureView

urlpatterns = [
    re_path(
        rf"^{settings.COURSE_ID_PATTERN}/$",
        CourseStructureView.as_view(),
        name="course_structure_api",
    ),
]
