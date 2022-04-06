"""
External checkout API endpoint urls.
"""

from django.urls import re_path

from ol_openedx_checkout_external.views import external_checkout

urlpatterns = [
    re_path(r"^", external_checkout, name="checkout_external"),
]
