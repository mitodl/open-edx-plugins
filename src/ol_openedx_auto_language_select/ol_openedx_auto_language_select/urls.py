"""
URL configuration for ol_openedx_auto_language_select app.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_auto_language_select.views import CourseLanguageView

urlpatterns = [
    re_path(
        rf"api/course-language/{settings.COURSE_KEY_PATTERN}$",
        CourseLanguageView.as_view(),
        name="ol_course_language",
    ),
]
