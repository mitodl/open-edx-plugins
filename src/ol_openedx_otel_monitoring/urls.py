"""
OTel Monitoring API endpoint urls.
"""

from django.urls import path
from ol_openedx_otel_monitoring import views

urlpatterns = [
    path("otel/healthcheck/", views.otel_health_check, name="otel_health_check"),
]
