"""
Course outline endpoint urls.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_course_outline_api.views import CourseOutlineView

urlpatterns = [
    re_path(
        rf"^{settings.COURSE_ID_PATTERN}/$",
        CourseOutlineView.as_view(),
        name="course_outline_api",
    ),
]
