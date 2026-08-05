# CLAUDE.md — ol_openedx_otel_monitoring

A Django app plugin (LMS + CMS) that wires OpenTelemetry tracing and metrics
into edx-platform via `opentelemetry-instrumentation-django`, with a
health-check endpoint to verify traces are flowing. Exporters (Console or
OTLP/HTTP) and resource attributes are all configured through Django
settings rather than code changes.

## Key files
- `ol_openedx_otel_monitoring/client.py`: `initialize_otel()` — entry point
  called from `AppConfig.ready()`; reads `settings.OTEL_CONFIGS`,
  conditionally calls `setup_tracing()` / `prepare_metrics()`, and
  instruments Django (optionally with SQLCommenter).
- `ol_openedx_otel_monitoring/tracing.py`: builds the tracer
  provider/span processor and exporter from `OTEL_TRACES_EXPORTER_MAPPING`.
- `ol_openedx_otel_monitoring/metrics.py`: `prepare_metrics()` — analogous
  setup for the metrics provider/exporter from
  `OTEL_METRICS_EXPORTER_MAPPING`.
- `ol_openedx_otel_monitoring/middleware.py`: `OTelMonitoringMiddleware` —
  currently just a pass-through subclass of the library's
  `_DjangoMiddleware`, explicitly left as a blueprint for future custom
  cache/memory tracing (see inline TODO referencing
  `mitodl/ol-infrastructure#827`).
- `ol_openedx_otel_monitoring/views.py` + `urls.py`: exposes
  `GET /otel/healthcheck/` to confirm the plugin is live and traced.
- `ol_openedx_otel_monitoring/exceptions.py`: `ConfigurationError` /
  `InitializationError` / `InstrumentationError` raised when
  `OTEL_CONFIGS` is missing or instrumentation setup fails.
- `ol_openedx_otel_monitoring/settings/common.py`: sets all default
  `OTEL_*` / `SQLCOMMENTER_*` settings (see below); `settings/production.py`
  overrides for prod deployment.
- `ol_openedx_otel_monitoring/apps.py`: `OTelMonitoringConfig` — registers
  settings + URLs for both LMS and CMS and calls `initialize_otel()` in
  `ready()`.

## Entry points & settings
- Registers on both `lms.djangoapp` and `cms.djangoapp` entry points (same
  `OTelMonitoringConfig` class for both).
- Central config dict: `settings.OTEL_CONFIGS` — `OTEL_ENABLED`,
  `OTEL_TRACES_ENABLED`, `OTEL_METRICS_ENABLED`, `TRACES_EXPORTER` /
  `METRICS_EXPORTER` (keys into the exporter mapping dicts, default
  `"console"`), `OTEL_INSTRUMENTATION_SQLCOMMENTER_ENABLED`.
- Exporter selection: `OTEL_TRACES_EXPORTER_MAPPING` /
  `OTEL_METRICS_EXPORTER_MAPPING` map exporter names (`console`,
  `richconsole`, `otlphttp`) to fully-qualified exporter classes — extend
  these dicts to add a new exporter.
- OTLP endpoint config: `OTEL_EXPORTER_OTLP_TRACES_ENDPOINT` /
  `..._METRICS_ENDPOINT` (or the shared `OTEL_EXPORTER_OTLP_ENDPOINT`), plus
  `..._HEADERS`, `..._PROTOCOL` (only `http/protobuf` currently supported),
  `..._CERTIFICATE`, `..._TIMEOUT`, `..._COMPRESSION`.
- Resource attributes: `OTEL_TRACES_RESOURCE_ATTRIBUTE` /
  `OTEL_METRICS_RESOURCE_ATTRIBUTE` (e.g. `service.name`).
- Django instrumentation tuning: `OTEL_PYTHON_DJANGO_EXCLUDED_URLS`,
  `OTEL_PYTHON_DJANGO_TRACED_REQUEST_ATTRS`,
  `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST/RESPONSE`,
  `OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS` (defaults
  sanitize `.*session.*,set-cookie`).
- SQLCommenter toggles:
  `SQLCOMMENTER_WITH_FRAMEWORK/CONTROLLER/ROUTE/APP_NAME/OPENTELEMETRY/DB_DRIVER`.
- No dedicated test settings module / test suite present in this plugin (no
  `tests/` directory).

## Notes
- Requires several OTel packages beyond the core dependency list per the
  README (`opentelemetry-exporter-richconsole`,
  `opentelemetry-exporter-otlp-proto-http`) — already declared in
  `pyproject.toml`.
- `initialize_otel()` raises `ConfigurationError` if `OTEL_CONFIGS` is
  absent entirely — the plugin is not a silent no-op if misconfigured, it
  errors at startup.
- Verify functionality by hitting `/otel/healthcheck/` and checking the
  configured exporter (Console prints to stdout locally; OTLP needs a
  reachable collector endpoint).
- `GRAFANA_INSTANCE_ID` / `GRAFANA_TOKEN` settings in `settings/common.py`
  are confirmed unused: set to empty strings there and never read anywhere
  else in the plugin. Actual OTLP auth goes through the
  `OTEL_EXPORTER_OTLP_*_HEADERS` settings instead — treat these two as
  vestigial rather than a Grafana integration point.
