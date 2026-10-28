"""
URLs for ol_openedx_chat.
"""

from django.conf import settings
from django.urls import re_path

from ol_openedx_chat.views import ContactUsEnabledView

urlpatterns = [
    re_path(
        r"ol-openedx-chat/api/contact-us-enabled/?$",
        ContactUsEnabledView.as_view(),
        name="ol_contact_us_enabled",
    ),
    re_path(
        rf"ol-openedx-chat/api/contact-us-enabled/{settings.COURSE_KEY_PATTERN}/?$",
        ContactUsEnabledView.as_view(),
        name="ol_contact_us_enabled_course",
    ),
]
