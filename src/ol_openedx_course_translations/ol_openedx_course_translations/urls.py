"""
URL configuration for ol_openedx_course_translations app.
"""

from django.urls import re_path, path
from django.conf import settings

from ol_openedx_course_translations.views import CourseLanguageView, ResetUserLanguageView

urlpatterns = [
    re_path(
        fr"course-language/{settings.COURSE_KEY_PATTERN}$",
        CourseLanguageView.as_view(),
        name="ol_openedx_course_language",
    ),
    path(
        "user/reset-language/",
        ResetUserLanguageView.as_view(),
        name="ol_openedx_reset_user_language",
    ),
]
