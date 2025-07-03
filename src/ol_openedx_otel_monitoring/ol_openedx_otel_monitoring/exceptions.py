class OpenTelemetryError(Exception):
    """Base class for all OTel related exceptions."""


class InstrumentationError(OpenTelemetryError):
    """Raised when there's an issue during instrumentation."""


class InitializationError(OpenTelemetryError):
    """Raised when there's an issue during initialization."""


class ConfigurationError(OpenTelemetryError):
    """Raised when there's a misconfiguration."""


class ExporterError(OpenTelemetryError):
    """Raised when an exporter is unsupported or not found."""


class EnvironmentVariableError(OpenTelemetryError):
    """Raised when a required env var is not found."""
