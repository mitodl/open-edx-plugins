"""
URLs for edx_sysadmin.
"""

from django.urls import re_path

from edx_sysadmin.api.views import (
    GitCourseDetailsAPIView,
    GitReloadAPIView,
)

app_name = "api"

urlpatterns = [
    re_path("^gitreload/$", GitReloadAPIView.as_view(), name="git-reload"),
    re_path(
        "^gitcoursedetails/$",
        GitCourseDetailsAPIView.as_view(),
        name="git-course-details",
    ),
]
