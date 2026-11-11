"""Tests for building and using the otlphttp trace and metric exporters."""

import pytest
import responses
from ol_openedx_otel_monitoring.exceptions import ConfigurationError
from ol_openedx_otel_monitoring.metrics import get_metric_exporter
from ol_openedx_otel_monitoring.tracing import get_trace_exporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor


def _export_span(exporter):
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    with provider.get_tracer(__name__).start_as_current_span("test-span"):
        pass
    provider.shutdown()


def _export_metric(exporter):
    # A long interval leaves the single export to shutdown().
    reader = PeriodicExportingMetricReader(exporter, export_interval_millis=10**9)
    provider = MeterProvider(metric_readers=[reader])
    provider.get_meter(__name__).create_counter("test-counter").add(1)
    provider.shutdown()


SIGNALS = [
    pytest.param(get_trace_exporter, _export_span, "TRACES", id="traces"),
    pytest.param(get_metric_exporter, _export_metric, "METRICS", id="metrics"),
]


@pytest.mark.parametrize(("get_exporter", "export", "signal"), SIGNALS)
@pytest.mark.parametrize(
    "headers",
    [
        None,
        '{"Authorization": "Basic abc123", "X-Scope-OrgID": 12345}',
        {"Authorization": "Basic abc123", "X-Scope-OrgID": 12345},
    ],
    ids=["http", "https-json-string", "https-dict"],
)
@responses.activate
def test_otlphttp_exports(settings, get_exporter, export, signal, headers):
    """The exporter posts to the endpoint, with headers only over https."""
    scheme = "https" if headers else "http"
    endpoint = f"{scheme}://collector/v1/{signal.lower()}"
    setattr(settings, f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT", endpoint)
    setattr(settings, f"OTEL_EXPORTER_OTLP_{signal}_HEADERS", headers)
    responses.post(endpoint)

    export(get_exporter("otlphttp"))

    assert [call.request.url for call in responses.calls] == [endpoint]
    sent = responses.calls[0].request.headers
    expected = ("Basic abc123", "12345") if headers else (None, None)
    assert (sent.get("Authorization"), sent.get("X-Scope-OrgID")) == expected


@pytest.mark.parametrize(
    ("get_exporter", "signal"),
    [(get_trace_exporter, "TRACES"), (get_metric_exporter, "METRICS")],
    ids=["traces", "metrics"],
)
@pytest.mark.parametrize(
    "headers",
    ["not json", '["Authorization"]'],
    ids=["invalid-json", "json-list"],
)
def test_https_endpoint_rejects_bad_headers(settings, get_exporter, signal, headers):
    """Headers that are not a JSON object fail at startup."""
    setattr(settings, f"OTEL_EXPORTER_OTLP_{signal}_ENDPOINT", "https://collector")
    setattr(settings, f"OTEL_EXPORTER_OTLP_{signal}_HEADERS", headers)

    with pytest.raises(ConfigurationError, match=f"OTEL_EXPORTER_OTLP_{signal}"):
        get_exporter("otlphttp")
