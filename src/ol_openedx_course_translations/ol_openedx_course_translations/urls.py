"""
URL configuration for ol_openedx_course_translations app.
"""

from django.urls import path

from ol_openedx_course_translations.views import CourseLanguageView

urlpatterns = [
    path(
        "course-language/",
        CourseLanguageView.as_view(),
        name="ol_openedx_course_language",
    ),
]
