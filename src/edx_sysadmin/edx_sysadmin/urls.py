"""
URLs for edx_sysadmin.
"""

from django.urls import include, re_path

from edx_sysadmin.views import (
    CoursesPanel,
    GitImport,
    GitLogs,
    SysadminDashboardRedirectionView,
    UsersPanel,
)

app_name = "sysadmin"


urlpatterns = [
    re_path("^$", SysadminDashboardRedirectionView.as_view(), name="sysadmin"),
    re_path(r"^courses/?$", CoursesPanel.as_view(), name="courses"),
    re_path(r"^gitimport/$", GitImport.as_view(), name="gitimport"),
    re_path(r"^gitlogs/?$", GitLogs.as_view(), name="gitlogs"),
    re_path(r"^gitlogs/(?P<course_id>.+)$", GitLogs.as_view(), name="gitlogs_detail"),
    re_path(r"^users/$", UsersPanel.as_view(), name="users"),
    re_path(r"^api/", include("edx_sysadmin.api.urls", namespace="api")),
]
