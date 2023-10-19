"""
Module for setting up and managing OpenTelemetry tracing configurations.

This module provides functionality to configure and initialize tracing exporters
for OpenTelemetry, suitable for use in Django applications.

WARNING: By default, this module uses 'ConsoleSpanExporter' as an exporter.
For production environments, it is recommended to configure
a more suitable exporter, such as 'otlp'.
"""
import logging
from importlib import import_module
from urllib.parse import urlparse

from django.conf import settings
from ol_openedx_otel_monitoring.exceptions import (
    ConfigurationError,
    EnvironmentVariableError,
    ExporterError,
    InitializationError,
    InstrumentationError,
)
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

# Configure logger for this module
logger = logging.getLogger(__name__)


def get_trace_exporter(exporter):
    """
    Retrieve and initialize a trace exporter based on a given exporter name.

    Args:
        exporter (str): Name of the exporter to be used.

    Returns:
        An instance of the requested exporter class.

    Raises:
        ExporterError: If there is an issue importing the exporter module.
        EnvironmentVariableError: If required environment variables are not set.
        ConfigurationError: If there is an error configuring the exporter.
    """
    try:
        # Dynamically load the exporter class from the module
        module_path, class_name = settings.OTEL_TRACES_EXPORTER_MAPPING[
            exporter
        ].rsplit(".", 1)
        module = import_module(module_path)
        ExporterClass = getattr(module, class_name)
    except ImportError as e:
        error_message = f"Error importing exporter module: {e!s}"
        logger.exception(error_message)
        raise ExporterError(error_message) from e

    try:
        # Configuration for 'otlphttp' exporter
        if exporter == "otlphttp":
            # Handle endpoint configuration and headers
            endpoint = settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT
            if endpoint is None:
                error_message = (
                    "OTEL_EXPORTER_OTLP_TRACES_ENDPOINT environment variable not set"
                )
                logger.exception(error_message)
                raise EnvironmentVariableError(error_message)

            if urlparse(endpoint).scheme == "https":
                headers = settings.OTEL_EXPORTER_OTLP_TRACES_HEADERS
                if headers is None:
                    error_message = (
                        "OTEL_EXPORTER_OTLP_TRACES_HEADERS environment variable not set"
                    )
                    logger.exception(error_message)
                    raise EnvironmentVariableError(error_message)
                return ExporterClass(endpoint=endpoint, headers=headers)

            return ExporterClass(endpoint=endpoint, insecure=True)
        # Default exporter configuration
        return ExporterClass()
    except ExporterError as e:
        error_message = f"Error configuring exporter: {e!s}"
        logger.exception(error_message)
        raise ConfigurationError(error_message) from e


def setup_tracing():
    """
    Set up and initialize tracing with a specified exporter and BatchSpanProcessor.

    Raises:
        InstrumentationError: If there is an error during the setup process.
    """
    try:
        # Resource configuration for tracing
        resource = Resource.create(attributes=settings.OTEL_TRACES_RESOURCE_ATTRIBUTE)

        # Validate and get the configured traces exporter
        trace_exporter = settings.OTEL_CONFIGS.get("TRACES_EXPORTER").lower()
        if trace_exporter not in settings.OTEL_TRACES_EXPORTER_MAPPING:
            error_message = f"Unsupported exporter: {trace_exporter}"
            logger.exception(error_message)
            raise ExporterError(error_message)

        # Initialize exporter and TracerProvider
        exporter_class = get_trace_exporter(trace_exporter)
        trace_processor = BatchSpanProcessor(exporter_class)
        trace_provider = TracerProvider(resource=resource)
        trace_provider.add_span_processor(trace_processor)
        trace.set_tracer_provider(trace_provider)
    except InitializationError as e:
        error_message = f"Error during traces instrumentation setup: {e!s}"
        logger.exception(error_message)
        raise InstrumentationError(error_message) from e
