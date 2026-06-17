"""
URLs for ol_openedx_rapid_response_reports.
"""

from django.urls import re_path

from ol_openedx_rapid_response_reports.api import (
    get_rapid_response_report,
    list_rapid_response_runs,
)

urlpatterns = [
    # rapid response runs listing (JSON)
    re_path(
        r"rapid_response_runs$",
        list_rapid_response_runs,
        name="list_rapid_response_runs",
    ),
    # rapid response downloads
    re_path(
        r"rapid_response_report/(?P<run_id>[^/]*)$",
        get_rapid_response_report,
        name="get_rapid_response_report",
    ),
]
