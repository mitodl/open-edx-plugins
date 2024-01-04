"""
Extends the built-in OTel monitoring middleware allowing for future customization.
Currently serves as a blueprint.
"""

from opentelemetry.instrumentation.django.middleware.otel_middleware import (
    _DjangoMiddleware,
)


class OTelMonitoringMiddleware(_DjangoMiddleware):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)


# (Shahbaz Shabbir): Implement custom logic for cache and memory tracing.
# https://github.com/mitodl/ol-infrastructure/issues/827
