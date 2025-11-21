"""
OL Open edX LTI Utilities URLs
"""

from django.urls import re_path

from ol_openedx_lti_utilities.views import LtiUserFixView

urlpatterns = [
    re_path(
        r"^",
        LtiUserFixView.as_view(),
        name="lti_user_fix",
    ),
]
