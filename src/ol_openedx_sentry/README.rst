OL OpenedX Sentry
#################

A Django app plugin that configures the `Sentry <https://sentry.io/>`_ SDK for
Open edX (both the LMS and the CMS). The plugin initializes the SDK from
``ENV_TOKENS`` when a DSN is present; when no DSN is configured it is a complete
no-op, so it is safe to install everywhere and enable per deployment.

On top of a bare ``sentry_sdk.init``, the plugin adds a fail-open ``before_send``
filter that drops operator-configured exception types and message regexes,
stamps OpenTelemetry trace context onto every event so Sentry issues correlate
with the structured logs shipped by ``ol_openedx_logging``, and configures the
``LoggingIntegration`` so ordinary log records do not turn into duplicate,
noisy Sentry issues.


Installation
============

Install the wheel into the LMS/CMS Python environment:

.. code-block:: bash

    pip install ol-openedx-sentry

or, with `uv <https://docs.astral.sh/uv/>`_:

.. code-block:: bash

    uv pip install ol-openedx-sentry

The plugin registers itself through the Open edX plugin system via the
``lms.djangoapp`` and ``cms.djangoapp`` entry points. There is no need to edit
``INSTALLED_APPS`` or wire up settings by hand; the plugin's ``plugin_settings``
hook runs automatically during settings resolution and initializes Sentry when a
DSN is present.


Configuration
=============

All configuration is read from ``ENV_TOKENS`` (typically populated from your
deployment's ``lms.yml`` / ``cms.yml`` or equivalent). ``SENTRY_DSN`` is the
master switch: if it is empty or unset, no other setting is read and the SDK is
never initialized.

.. list-table::
   :header-rows: 1
   :widths: 30 15 55

   * - ``ENV_TOKENS`` key
     - Default
     - Meaning
   * - ``SENTRY_DSN``
     - ``""``
     - Sentry Data Source Name. Required to enable the plugin. When empty the
       plugin is a no-op and nothing else below is read.
   * - ``SENTRY_ENVIRONMENT``
     - ``None``
     - Sentry environment name (e.g. ``production``, ``staging``). Passed
       straight to ``sentry_sdk.init(environment=...)``.
   * - ``SENTRY_TRACES_SAMPLE_RATE``
     - ``0``
     - Performance-tracing sample rate (0.0-1.0). ``0`` disables performance
       tracing; operators opt in per deployment.
   * - ``SENTRY_RELEASE_SPECIFIER``
     - ``None``
     - Release identifier, passed to ``sentry_sdk.init(release=...)`` for
       associating events with a build.
   * - ``SENTRY_SEND_HTTP_REQUEST_BODIES``
     - ``"small"``
     - Maps to the SDK's ``max_request_body_size`` (``"never"``, ``"small"``,
       ``"medium"``, ``"always"``).
   * - ``SENTRY_SEND_DEFAULT_PII``
     - ``False``
     - When ``True``, attaches identifying data (user id, username, client IP)
       to events. Off by default for FERPA/privacy reasons; operators opt in
       per deployment.
   * - ``SENTRY_IGNORED_EXCEPTION_CLASSES``
     - ``[]``
     - List of dotted import paths (e.g. ``requests.exceptions.HTTPError``) or
       builtin names (e.g. ``ValueError``) of exception classes to drop.
       Matching uses ``issubclass``, so subclasses are dropped too. Paths that
       cannot be resolved to a ``BaseException`` subclass are logged and
       skipped, never blackholing reporting.
   * - ``SENTRY_IGNORED_EXCEPTION_MESSAGES``
     - ``[]``
     - List of regexes matched with ``re.search`` against the exception message
       *and* against log-only event messages. Each entry may be a single string
       or a list/tuple of strings (each element is treated as its own pattern,
       which tolerates configs that split a message into adjacent YAML
       fragments). Invalid regexes are logged and skipped.
   * - ``SENTRY_LOG_EVENT_LEVEL``
     - ``None``
     - Controls ``LoggingIntegration.event_level``. The default of ``None``
       means log records never become standalone Sentry issues (they remain
       breadcrumbs only). Set to a level name such as ``"ERROR"`` to restore
       log-as-event capture. An unrecognized value is logged and treated as
       ``None``.

Example ``ENV_TOKENS`` fragment:

.. code-block:: yaml

    SENTRY_DSN: "https://examplekey@o0.ingest.sentry.io/0"
    SENTRY_ENVIRONMENT: "production"
    SENTRY_RELEASE_SPECIFIER: "edx-platform@2026.07.15"
    SENTRY_TRACES_SAMPLE_RATE: 0.05
    SENTRY_SEND_DEFAULT_PII: false
    SENTRY_IGNORED_EXCEPTION_CLASSES:
      - "django.http.Http404"
      - "requests.exceptions.HTTPError"
    SENTRY_IGNORED_EXCEPTION_MESSAGES:
      - "Broken pipe"
      - "Connection reset by peer"


Behavior notes / design decisions
=================================

**``before_send`` is fail-open.** The event filter drops events whose raised
exception is a subclass of an ignored class, or whose message matches an ignored
regex. If the filter itself raises for any reason, the error is logged and the
original event is returned unfiltered. A bug in filtering can never silently
blackhole error reporting. Relatedly, ignored classes and message regexes are
resolved and compiled once at init time (not per event), so a bad import path or
invalid regex is reported once and skipped rather than raising inside
``before_send``.

**LoggingIntegration is configured explicitly with ``event_level=None``.** By
default the Sentry SDK promotes ``ERROR``-and-above log records into standalone
issues. Because Open edX (via ``ol_openedx_logging``) emits structured
structlog/stdlib logs heavily, that default produces duplicate and noisy Sentry
issues. This plugin therefore installs ``LoggingIntegration(level=INFO,
event_level=None)`` so log records become breadcrumbs only. Uncaught exceptions
are still captured by the Django integration, so real errors are not lost.
Operators who want the old log-as-event behavior can set
``SENTRY_LOG_EVENT_LEVEL``.

**OpenTelemetry trace context is stamped onto every event.** When a valid,
recording span is active, the event filter tags each event with ``trace_id`` and
``span_id`` using the same formatting that ``ol_openedx_logging`` applies to its
structured logs. Sentry issues and the corresponding logs in Loki therefore
correlate on identical values. ``opentelemetry`` is a soft dependency: if it is
not installed (or there is no active recording span) the tagging is simply
skipped. The plugin deliberately does not import ``ol_openedx_logging`` so the
two plugins stay independent.

**Sentry's structured Logs feature is intentionally left OFF.** The plugin does
not enable ``enable_logs`` / ``_experiments`` log ingestion. Application logs
already ship to Loki via ``ol_openedx_logging``, so enabling Sentry Logs would
double-ingest the same records. Sentry is used for error and (optionally)
performance data; Loki remains the system of record for logs.
