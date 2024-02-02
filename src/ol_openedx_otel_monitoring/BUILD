python_sources(
    name="otel_monitoring",
    dependencies=[
        "src/ol_openedx_otel_monitoring/settings:plugin_settings",
        "//:external_dependencies#opentelemetry-distro",
        "//:external_dependencies#opentelemetry-instrumentation-django",
        "//:external_dependencies#opentelemetry-exporter-richconsole",
        "//:external_dependencies#opentelemetry-exporter-otlp-proto-http",
    ],
)

python_distribution(
    name="otel_monitoring_package",
    dependencies=[":otel_monitoring"],
    provides=setup_py(
        name="ol-openedx-otel-monitoring",
        version="0.1.1",
        description="OTel Monitoring",
        license="BSD-3-Clause",
        entry_points={
            "lms.djangoapp": [
                "ol_openedx_otel_monitoring = ol_openedx_otel_monitoring.apps:OTelMonitoringConfig"
            ],
            "cms.djangoapp": [
                "ol_openedx_otel_monitoring = ol_openedx_otel_monitoring.apps:OTelMonitoringConfig"
            ],
        },
    ),
)
