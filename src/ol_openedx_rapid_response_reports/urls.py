"""
URLs for ol_openedx_rapid_response_reports.
"""
from django.conf.urls import url

from ol_openedx_rapid_response_reports.api import get_rapid_response_report

urlpatterns = [
    # rapid response downloads
    url(
        r"rapid_response_report/(?P<run_id>[^/]*)$",
        get_rapid_response_report,
        name="get_rapid_response_report",
    ),
]
