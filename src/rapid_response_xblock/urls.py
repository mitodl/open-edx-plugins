"""
External checkout API endpoint urls.
"""

from django.urls import re_path

from rapid_response_xblock.views import toggle_rapid_response

urlpatterns = [
    re_path(r"^", toggle_rapid_response, name="toggle_rapid_response"),
]
