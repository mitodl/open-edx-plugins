"""
URLs for edx_sysadmin.
"""
from django.conf.urls import include, url
from edx_sysadmin.views import (
    CoursesPanel,
    GitImport,
    GitLogs,
    SysadminDashboardRedirectionView,
    UsersPanel,
)

app_name = "sysadmin"


urlpatterns = [
    url("^$", SysadminDashboardRedirectionView.as_view(), name="sysadmin"),
    url(r"^courses/?$", CoursesPanel.as_view(), name="courses"),
    url(r"^gitimport/$", GitImport.as_view(), name="gitimport"),
    url(r"^gitlogs/?$", GitLogs.as_view(), name="gitlogs"),
    url(r"^gitlogs/(?P<course_id>.+)$", GitLogs.as_view(), name="gitlogs_detail"),
    url(r"^users/$", UsersPanel.as_view(), name="users"),
    url(r"^api/", include("edx_sysadmin.api.urls", namespace="api")),
]
