"""
URLs for edx_sysadmin.
"""

from django.urls import path

from edx_sysadmin.api.views import (
    GitCourseDetailsAPIView,
    GitReloadAPIView,
)

app_name = "api"

urlpatterns = [
    path("gitreload/", GitReloadAPIView.as_view(), name="git-reload"),
    path(
        "gitcoursedetails/",
        GitCourseDetailsAPIView.as_view(),
        name="git-course-details",
    ),
]
