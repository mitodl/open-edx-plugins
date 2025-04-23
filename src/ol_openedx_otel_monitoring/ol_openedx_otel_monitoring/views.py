"""Views for OTel Monitoring"""

from django.http import JsonResponse


def otel_health_check(_):
    """Provide a simple health check endpoint related to OTel."""

    # (TODO-Shahbaz Shabbir): Implement actual health checks for OTel.
    # https://github.com/mitodl/ol-infrastructure/issues/827

    return JsonResponse({"status": "healthy"})
