"""
URL configuration for ol_openedx_course_translations app.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_course_translations.views import CourseLanguageView

urlpatterns = [
    re_path(
        rf"api/course-language/{settings.COURSE_KEY_PATTERN}$",
        CourseLanguageView.as_view(),
        name="ol_openedx_course_language",
    ),
]
