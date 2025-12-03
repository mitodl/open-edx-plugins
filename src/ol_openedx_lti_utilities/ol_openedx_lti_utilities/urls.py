"""
OL Open edX LTI Utilities URLs
"""

from django.conf import settings
from django.urls import re_path

if settings.FEATURES.get("ENABLE_LTI_PROVIDER"):
    from ol_openedx_lti_utilities.views import LtiUserFixView

    urlpatterns = [
        re_path(
            r"^",
            LtiUserFixView.as_view(),
            name="lti_user_fix",
        ),
    ]
