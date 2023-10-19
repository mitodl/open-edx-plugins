"""
Module for setting up and managing OpenTelemetry metrics configurations
in a Django application.

This module facilitates the configuration and initialization of metrics
exporters based on settings defined in Django.

WARNING: By default, this uses 'ConsoleMetricExporter' as an exporter.
For production environments, it's recommended to configure a more
appropriate exporter, such as 'otlp'.
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
from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

logger = logging.getLogger(__name__)


def get_metric_exporter(exporter):
    """
    Retrieve and initialize the metric exporter based on the given exporter name.

    Args:
        exporter (str): The name of the exporter to initialize.

    Returns:
        An instance of the specified exporter class.

    Raises:
        ExporterError: If there's an issue importing the exporter module.
        ConfigurationError: If there's an issue configuring the exporter.
        EnvironmentVariableError: If required environment variables are not set.
    """
    try:
        # Dynamically load the exporter class from the module
        module_path, class_name = settings.OTEL_METRICS_EXPORTER_MAPPING[
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
            endpoint = settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT
            if endpoint is None:
                error_message = (
                    "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT environment variable not set"
                )
                logger.exception(error_message)
                raise EnvironmentVariableError(error_message)

            if urlparse(endpoint).scheme == "https":
                headers = settings.OTEL_EXPORTER_OTLP_METRICS_HEADERS
                if headers is None:
                    error_message = (
                        "OTEL_EXPORTER_OTLP_METRICS_HEADERS "
                        "environment variable not set"
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


def prepare_metrics():
    """
    Prepare and set up metrics collection for the application.

    This function reads the METRICS_EXPORTER configuration from Django settings,
    initializes the specified exporter, and sets up the MeterProvider.

    Raises:
        InstrumentationError: If there's an error during the setup process.
    """
    try:
        # Setup resource for MeterProvider
        resource = Resource.create(attributes=settings.OTEL_METRICS_RESOURCE_ATTRIBUTE)

        # Validate and get the configured metric exporter
        metric_exporter = settings.OTEL_CONFIGS.get("METRICS_EXPORTER").lower()
        if metric_exporter not in settings.OTEL_METRICS_EXPORTER_MAPPING:
            error_message = f"Unsupported exporter: {metric_exporter}"
            logger.exception(error_message)
            raise ExporterError(error_message)

        # Initialize exporter and MeterProvider
        exporter_class = get_metric_exporter(metric_exporter)
        metric_reader = PeriodicExportingMetricReader(exporter_class)
        metric_provider = MeterProvider(
            resource=resource, metric_readers=[metric_reader]
        )
        metrics.set_meter_provider(metric_provider)
    except InitializationError as e:
        error_message = f"Error during metrics instrumentation setup: {e!s}"
        logger.exception(error_message)
        raise InstrumentationError(error_message) from e
