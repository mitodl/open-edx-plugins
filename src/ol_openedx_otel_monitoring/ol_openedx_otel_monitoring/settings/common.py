"""Common settings unique to the OTel monitoring plugin."""


def plugin_settings(settings):
    """Settings for the Otel monitoring plugin."""  # noqa: D401

    # Enabling this flag will add django framework, and it's version
    settings.SQLCOMMENTER_WITH_FRAMEWORK = True
    # Enabling this flag will add controller name that handles the request
    settings.SQLCOMMENTER_WITH_CONTROLLER = True
    # Enabling this flag will add url path that handles the request
    settings.SQLCOMMENTER_WITH_ROUTE = True
    # Enabling this flag will add app name that handles the request
    settings.SQLCOMMENTER_WITH_APP_NAME = True
    # Enabling this flag will add open-telemetry transparent
    settings.SQLCOMMENTER_WITH_OPENTELEMETRY = True
    # Enabling this flag will add name of the db driver
    settings.SQLCOMMENTER_WITH_DB_DRIVER = True
    # To exclude certain URLs from tracking
    settings.OTEL_PYTHON_DJANGO_EXCLUDED_URLS = "healthcheck"
    # To extract attributes from Django's request object
    settings.OTEL_PYTHON_DJANGO_TRACED_REQUEST_ATTRS = "path_info,content_type"
    # To capture HTTP request headers as span attributes
    # e.g. content-type,custom_request_header,Accept.*,X-.*,.*
    settings.OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST = ".*"
    # To capture HTTP response headers as span attributes,
    # e.g. content-type,custom_response_header,Content.*,X-.*,.*
    settings.OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE = ".*"
    # To prevent storing sensitive data e.g. .*session.*,set-cookie
    settings.OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS = (
        ".*session.*,set-cookie"
    )

    settings.OTEL_CONFIGS = {
        "OTEL_ENABLED": True,
        "OTEL_TRACES_ENABLED": True,
        "OTEL_METRICS_ENABLED": True,
        "TRACES_EXPORTER": "console",
        "METRICS_EXPORTER": "console",
        "OTEL_INSTRUMENTATION_SQLCOMMENTER_ENABLED": False,
    }

    settings.OTEL_TRACES_EXPORTER_MAPPING = {
        "console": "opentelemetry.sdk.trace.export.ConsoleSpanExporter",
        "richconsole": "opentelemetry.exporter.richconsole.RichConsoleSpanExporter",
        "otlphttp": "opentelemetry.exporter.otlp.proto.http.trace_exporter."
        "OTLPSpanExporter",
    }

    settings.OTEL_METRICS_EXPORTER_MAPPING = {
        "console": "opentelemetry.sdk.metrics.export.ConsoleMetricExporter",
        "otlphttp": "opentelemetry.exporter.otlp.proto.http.metric_exporter."
        "OTLPMetricExporter",
    }

    settings.OTEL_TRACES_RESOURCE_ATTRIBUTE = {
        "service.name": "ol_openedx_otel_traces_monitoring",
    }
    settings.OTEL_METRICS_RESOURCE_ATTRIBUTE = {
        "service.name": "ol_openedx_otel_metrics_monitoring",
    }

    settings.GRAFANA_INSTANCE_ID = ""
    settings.GRAFANA_TOKEN = ""

    settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://localhost:4318"
    settings.OTEL_EXPORTER_OTLP_TRACES_HEADERS = (
        '{"Authorization": "Basic <base64_encoded_string>"}'
    )
    settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT = "http://localhost:4318"
    settings.OTEL_EXPORTER_OTLP_METRICS_HEADERS = (
        '{"Authorization": "Basic <base64_encoded_string>"}'
    )
    settings.OTEL_EXPORTER_OTLP_TRACES_PROTOCOL = "http/protobuf"
    settings.OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE = True
    settings.OTEL_EXPORTER_OTLP_METRICS_CERTIFICATE = True
    settings.OTEL_EXPORTER_OTLP_TRACES_TIMEOUT = 10
    settings.OTEL_EXPORTER_OTLP_METRICS_TIMEOUT = 10
    settings.OTEL_EXPORTER_OTLP_TRACES_COMPRESSION = "none"
    settings.OTEL_EXPORTER_OTLP_METRICS_COMPRESSION = "none"
