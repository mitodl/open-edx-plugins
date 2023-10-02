"""
URLs for edx_sysadmin.
"""
from django.conf.urls import url
from edx_sysadmin.api.views import (
    GitCourseDetailsAPIView,
    GitReloadAPIView,
)

app_name = "api"

urlpatterns = [
    url("^gitreload/$", GitReloadAPIView.as_view(), name="git-reload"),
    url(
        "^gitcoursedetails/$",
        GitCourseDetailsAPIView.as_view(),
        name="git-course-details",
    ),
]
