"""
URLs for edx_sysadmin.
"""

from django.urls import include, path, re_path

from edx_sysadmin.views import (
    CoursesPanel,
    GitImport,
    GitLogs,
    SysadminDashboardRedirectionView,
    UsersPanel,
)

app_name = "sysadmin"


urlpatterns = [
    path("", SysadminDashboardRedirectionView.as_view(), name="sysadmin"),
    re_path(r"^courses/?$", CoursesPanel.as_view(), name="courses"),
    path("gitimport/", GitImport.as_view(), name="gitimport"),
    re_path(r"^gitlogs/?$", GitLogs.as_view(), name="gitlogs"),
    path("gitlogs/<path:course_id>", GitLogs.as_view(), name="gitlogs_detail"),
    path("users/", UsersPanel.as_view(), name="users"),
    path("api/", include("edx_sysadmin.api.urls", namespace="api")),
]
