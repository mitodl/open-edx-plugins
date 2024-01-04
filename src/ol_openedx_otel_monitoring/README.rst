.. note::

    This plugin has currently been tested only with the Console Exporter. Logging functionality is not yet integrated. Further development and testing are required for enhanced compatibility and features.


Opentelemetry Django Plugin
=============================

This Django plugin integrates Open Telemetry, offering both tracing and metric functionalities. It is built upon the `opentelemetry-instrumentation-django` package and adds the capability for manual instrumentation. Users can select different exporters for traces and metrics. Currently, it supports Console Exporter for local development and OTLP Exporter for exporting data to third-party platforms. A customizable blueprint middleware can be easily added via settings.


Installation
------------

You can install this plugin into any Open edX instance by using any of the following methods:


**Option 1: Install from PyPI**

.. code-block::

    # If running devstack in docker, first open a shell in LMS (make lms-shell)

    pip install ol-openedx-otel-monitoring


**Option 2: Build the package locally and install it**

Follow these steps in a terminal on your machine:

1. Navigate to ``open-edx-plugins`` directory
2. If you haven't done so already, run ``./pants build``
3. Run ``./pants package ::``. This will create a "dist" directory inside "open-edx-plugins" directory with ".whl" & ".tar.gz" format packages for all the "ol_openedx_*" plugins in "open-edx-plugins/src")
4. Move/copy any of the ".whl" or ".tar.gz" files for this plugin that were generated in the above step to the machine/container running Open edX (NOTE: If running devstack via Docker, you can use ``docker cp`` to copy these files into your CMS container)
5. Run a shell in the machine/container running Open edX, and install this plugin using pip

Configuration
------------

The plugin offers multiple settings for customization:

.. code-block:: python

    OTEL_CONFIGS = {
        "OTEL_ENABLED": True,
        "OTEL_TRACES_ENABLED": True,
        "OTEL_METRICS_ENABLED": True,
        "TRACES_EXPORTER": "console",
        "METRICS_EXPORTER": "console",
        "OTEL_INSTRUMENTATION_SQLCOMMENTER_ENABLED": False,
    }

`OTEL_CONFIGS` allows the following settings:

- `OTEL_ENABLED`: Enables or disables telemetry data export.
- `OTEL_TRACES_ENABLED`: Enables or disables traces telemetry data export.
- `OTEL_METRICS_ENABLED`: Enables or disables metrics telemetry data export.
- `TRACES_EXPORTER`: Defines the exporter for traces.
- `METRICS_EXPORTER`: Specifies the exporter for metrics.
- `OTEL_INSTRUMENTATION_SQLCOMMENTER_ENABLED`: Toggles SQLCommenter for Django instrumentation.

`Exporter mappings:`

The plugin allows dynamic selection and configuration of exporters for both traces and metrics:


.. code-block:: python

    OTEL_TRACES_EXPORTER_MAPPING = {
        "console": "opentelemetry.sdk.trace.export.ConsoleSpanExporter",
        "otlphttp": "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter",
    }

    OTEL_METRICS_EXPORTER_MAPPING = {
        "console": "opentelemetry.sdk.metrics.export.ConsoleMetricExporter",
        "otlphttp": "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter",
    }

To add a new exporter, include it in the appropriate mapping and select it in the configuration. Support for the new exporter must also be implemented in the plugin. Any additional settings required for the exporter should be added to the settings for easy access within the plugin.

`Resource Attributes:`

`OTEL_TRACES_RESOURCE_ATTRIBUTE`

This setting allows you to specify the resource attributes that should be associated with traces. It enhances trace data by providing additional context, making it easier to filter and analyze trace information.

.. code-block:: python

    OTEL_TRACES_RESOURCE_ATTRIBUTE = {
        'service.name': 'example-service',
        'service.instance.id': 'instance-1'
        # Other attributes can be added here
    }

`OTEL_METRICS_RESOURCE_ATTRIBUTE`

Similarly, it is used for specifying resource attributes for metrics. It helps in enriching metric data with useful information, aiding in the monitoring and analysis process.

.. code-block:: python

    OTEL_METRICS_RESOURCE_ATTRIBUTE = {
        'service.name': 'example-service',
        'service.instance.id': 'instance-1'
        # Additional attributes can be included here
    }

For more detailed information about these settings and how to use them, please refer to the following documentation:
`Resource semantic conventions <https://github.com/open-telemetry/semantic-conventions/blob/main/docs/resource/README.md#semantic-attributes-with-dedicated-environment-variable>`_
& `Resource SDK <https://github.com/open-telemetry/opentelemetry-specification/blob/v1.26.0/specification/resource/sdk.md#specifying-resource-information-via-an-environment-variable>`_



`OTLP exporter configuration:`

It is recommended to use separate settings for traces and metrics rather than generic settings. For example:

.. code-block:: python

    OTEL_EXPORTER_OTLP_ENDPOINT = "http://localhost:4318"

In this case, traces will automatically export to `<OTEL_EXPORTER_OTLP_ENDPOINT>/v1/traces` and metrics to `<OTEL_EXPORTER_OTLP_ENDPOINT>/v1/metrics`. However, if you require separate configurations for traces and metrics, you can use:

.. code-block:: python

    OTEL_EXPORTER_OTLP_TRACES_ENDPOINT = "http://localhost:4318/v1/traces"
    OTEL_EXPORTER_OTLP_METRICS_ENDPOINT = "http://localhost:4318/v1/metrics"

.. code-block:: python

    OTEL_EXPORTER_OTLP_TRACES_HEADERS = '{"Authorization": "Basic <base64_encoded_string>"}'
    OTEL_EXPORTER_OTLP_METRICS_HEADERS = '{"Authorization": "Basic <base64_encoded_string>"}'
    OTEL_EXPORTER_OTLP_TRACES_CERTIFICATE = True
    OTEL_EXPORTER_OTLP_METRICS_CERTIFICATE = True
    OTEL_EXPORTER_OTLP_TRACES_TIMEOUT = 10
    OTEL_EXPORTER_OTLP_METRICS_TIMEOUT = 10
    OTEL_EXPORTER_OTLP_TRACES_COMPRESSION = "none"
    OTEL_EXPORTER_OTLP_METRICS_COMPRESSION = "none"

This approach allows more flexibility and control over where each type of telemetry data is sent, especially useful in complex deployment environments.

As the plugin currently supports only OTLP HTTP, you need to specify the protocol:



.. code-block:: python

    OTEL_EXPORTER_OTLP_TRACES_PROTOCOL = "http/protobuf"

Future updates may include support for other protocols like gRPC.

`Settings related to Django instrumentation:`

.. code-block::

    To exclude certain URLs from tracking
    OTEL_PYTHON_DJANGO_EXCLUDED_URLS = "healthcheck"

    # To extract attributes from Django's request object
    OTEL_PYTHON_DJANGO_TRACED_REQUEST_ATTRS = "path_info,content_type"

    # To capture HTTP request headers as span attributes
    # e.g. content-type,custom_request_header,Accept.*,X-.*,.*
    OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_REQUEST = ".*"

    # To capture HTTP response headers as span attributes,
    # e.g. content-type,custom_response_header,Content.*,X-.*,.*
    OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SERVER_RESPONSE = ".*"

    # To prevent storing sensitive data e.g. .*session.*,set-cookie
    OTEL_INSTRUMENTATION_HTTP_CAPTURE_HEADERS_SANITIZE_FIELDS = ".*session.*,set-cookie"

`Configure SQLCommenter settings:`

.. code-block::

    # Enabling this flag will add django framework, and it's version
    SQLCOMMENTER_WITH_FRAMEWORK = True

    # Enabling this flag will add controller name that handles the request
    SQLCOMMENTER_WITH_CONTROLLER = True

    # Enabling this flag will add url path that handles the request
    SQLCOMMENTER_WITH_ROUTE = True

    # Enabling this flag will add app name that handles the request
    SQLCOMMENTER_WITH_APP_NAME = True

    # Enabling this flag will add open-telemetry transparent
    SQLCOMMENTER_WITH_OPENTELEMETRY = True

    # Enabling this flag will add name of the db driver
    SQLCOMMENTER_WITH_DB_DRIVER = True


In addition to Django, this plugin requires several OpenTelemetry-related packages ensure that the following packages are installed.

- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-instrumentation-django`
- `opentelemetry-exporter-richconsole`
- `opentelemetry-exporter-otlp-proto-http`



How To Use
----------

1. **Install the Plugin**: Begin by installing the Open Telemetry Django plugin in your Django project.

2. **Configure Necessary Settings**: Ensure all necessary settings are properly configured. This includes specifying the correct endpoints, exporters, and any Django or SQLCommenter specific settings as outlined in the previous sections.

3. **Test the Health Check Endpoint**: After installation and configuration, test the plugin's functionality by hitting the `/otel/healthcheck/` endpoint. This can be done using a browser or a tool like `curl`:

   .. code-block:: bash

       curl http://localhost:8000/otel/healthcheck/

   Replace `localhost:8000` with your actual server address. A successful hit to this endpoint will return a response, confirming that the plugin is healthy.

4. **Verify Traces**: Upon accessing the health check endpoint, you should be able to see the traces of this request in your configured trace exporter (e.g., Console or OTLP Exporter). This verifies that the plugin is not only installed but also actively tracing requests.


`Customizing Traces and Metrics`

To add custom data to traces and metrics, enhancing the utility of the telemetry data.

`Custom Traces`

To add custom data to your traces, use the Open Telemetry tracing API. Here's a basic example:

.. code-block:: python

    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
    with tracer.start_as_current_span("custom_span") as span:
        span.set_attribute("custom_attribute", "value")
        # Your custom code goes here

For more advanced tracing techniques and examples, refer to the `detailed tracing guide <https://opentelemetry.io/docs/instrumentation/python/manual/#creating-spans>`_.

`Custom Metrics`

Similarly, for metrics, utilize the Open Telemetry metrics API. Below is a simple example:

.. code-block:: python

    from opentelemetry import metrics

    meter = metrics.get_meter(__name__)
    custom_counter = meter.create_counter("custom_counter", description="Custom metric counter")

    def some_function():
        custom_counter.add(1)
        # Additional logic for your function

Explore more about metrics instrumentation in the `comprehensive metrics guide <https://opentelemetry.io/docs/instrumentation/python/manual/#creating-and-using-synchronous-instruments>`_

Refer to the `Open Telemetry Documentation <https://opentelemetry.io/docs/>`_ for more details and advanced usage instructions.
