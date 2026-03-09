"""
URL configuration for ol_openedx_auto_select_language app.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_auto_select_language.views import CourseLanguageView

urlpatterns = [
    re_path(
        rf"auto-select-language/api/course-language/{settings.COURSE_KEY_PATTERN}$",
        CourseLanguageView.as_view(),
        name="ol_course_language",
    ),
    # TODO: Remove the legacy endpoint in a  # noqa: FIX002, TD003, TD002
    #  future release after updating all clients to use the new endpoint.
    re_path(
        rf"/course-translations/api/course-language/{settings.COURSE_KEY_PATTERN}$",
        CourseLanguageView.as_view(),
        name="ol_course_language_legacy",
    ),
]
