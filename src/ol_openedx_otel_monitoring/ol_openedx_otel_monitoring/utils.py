"""Helpers shared by the tracing and metrics exporter setup."""

import json

from ol_openedx_otel_monitoring.exceptions import ConfigurationError


def parse_otlp_headers(headers, setting_name):
    """
    Return OTLP exporter headers as a dict of strings.

    The settings document headers as a JSON object string, but YAML
    ENV_TOKENS can also supply a mapping directly, so both are accepted.

    Raises:
        ConfigurationError: If headers is neither a dict nor a string holding
            a JSON object.
    """
    if isinstance(headers, str):
        try:
            headers = json.loads(headers)
        except json.JSONDecodeError as e:
            error_message = f"{setting_name} is not valid JSON: {e!s}"
            raise ConfigurationError(error_message) from e
    if not isinstance(headers, dict):
        error_message = f"{setting_name} must be a JSON object of headers"
        raise ConfigurationError(error_message)
    # YAML turns e.g. `X-Scope-OrgID: 12345` into an int; the exporter needs str.
    return {str(key): str(value) for key, value in headers.items()}
