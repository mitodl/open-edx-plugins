"""
This module initializes OpenTelemetry (OTel) for Django applications.

It configures tracing and metrics based on the settings defined in
Django's settings module.
It also supports enabling SQLCommenter instrumentation for Django.
"""
import logging

from django.conf import settings
from ol_openedx_otel_monitoring.exceptions import (
    ConfigurationError,
    InitializationError,
    InstrumentationError,
)
from ol_openedx_otel_monitoring.metrics import prepare_metrics
from ol_openedx_otel_monitoring.tracing import setup_tracing
from opentelemetry.instrumentation.django import DjangoInstrumentor

# Configure logger for this module
logger = logging.getLogger(__name__)


def initialize_otel():
    """
    Initialize OpenTelemetry instrumentation for Django.

    This function reads the OTEL configurations from Django settings and sets up
    tracing and metrics based on these configurations. It also instruments Django
    with SQLCommenter if enabled in the configurations.

    Raises:
        ConfigurationError: If OTEL configurations are missing in Django settings.
        InitializationError: If there is an error during the initialization process.
    """
    configs = getattr(settings, "OTEL_CONFIGS", None)

    if not configs:
        error_message = "Missing OTEL configs in settings."
        logger.exception(error_message)
        raise ConfigurationError(error_message)

    try:
        if configs.get("OTEL_ENABLED"):
            # Setup tracing and metrics if enabled in configurations
            if configs.get("OTEL_TRACES_ENABLED"):
                setup_tracing()
            if configs.get("OTEL_METRICS_ENABLED"):
                prepare_metrics()
            # Instrument Django with SQLCommenter if enabled
            if configs.get("OTEL_INSTRUMENTATION_SQLCOMMENTER_ENABLED", False):
                DjangoInstrumentor().instrument(is_sql_commentor_enabled=True)
            DjangoInstrumentor().instrument()
    except InstrumentationError as ie:
        error_message = (
            f"Failed to initialize OTel due to instrumentation error: {ie!s}"
        )
        logger.exception(error_message)
        raise InitializationError(error_message) from ie
