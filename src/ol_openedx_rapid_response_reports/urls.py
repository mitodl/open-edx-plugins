"""
URLs for ol_openedx_rapid_response_reports.
"""

from django.urls import re_path
from ol_openedx_rapid_response_reports.api import get_rapid_response_report

urlpatterns = [
    # rapid response downloads
    re_path(
        r"rapid_response_report/(?P<run_id>[^/]*)$",
        get_rapid_response_report,
        name="get_rapid_response_report",
    ),
]
