# CLAUDE.md — ol_openedx_logging

A Django app plugin that replaces edx-platform's default logging stack with `structlog`,
producing structured JSON logs (or colorized console output in DEBUG) and preserving the
platform's `tracking` handler/logger. It installs into both LMS and CMS via
`AppConfig.ready()` and also re-applies itself inside Celery worker processes.

## Key files
- `ol_openedx_logging/logging.py`: core of the plugin — `configure_structlog()` builds
  the structlog + stdlib `ProcessorFormatter` pipeline, preserves/rebuilds the edX
  `tracking` handler (falls back to a `RotatingFileHandler` if the platform's
  `SysLogHandler` targets a missing `/dev/log` socket), and
  `configure_from_logging_dict()` is the `LOGGING_CONFIG` entry point invoked before
  `apps.populate()`.
- `ol_openedx_logging/processors.py`: custom structlog processors —
  `inject_otel_context` (adds `trace_id`/`span_id` if `opentelemetry` is installed and a
  span is active) and `inject_k8s_context` (adds pod/namespace/node name from Downward
  API env vars, precomputed once at import).
- `ol_openedx_logging/celery.py`: `setup_celery_logging`, connected to Celery's
  `setup_logging` signal so structlog is re-applied (`force=True`) after Celery resets
  logging in worker processes.
- `ol_openedx_logging/app.py`: `EdxLoggingLMS` / `EdxLoggingCMS` AppConfigs — both call
  `configure_structlog()` in `ready()` and conditionally wire the Celery signal (no-op
  if Celery isn't installed).
- `ol_openedx_logging/settings/production.py`: `plugin_settings()` — forwards
  `EDXAPP_LOG_LEVEL` to `LOG_LEVEL` and sets `settings.LOGGING_CONFIG` to the plugin's
  entry point.
- `ol_openedx_logging/settings/test.py`: standalone minimal Django settings for the
  plugin's own unit tests.

## Entry points & settings
- Registers on both `lms.djangoapp` (`EdxLoggingLMS`) and `cms.djangoapp`
  (`EdxLoggingCMS`) entry points, each pointing `production` settings at
  `settings.production`.
- Env vars (read directly, not via `ENV_TOKENS`, except at settings-load time):
  `LOG_LEVEL` (root level, default `INFO`, takes precedence), `EDXAPP_LOG_LEVEL`
  (edX-style fallback, forwarded to `LOG_LEVEL` by `plugin_settings` if `LOG_LEVEL`
  isn't already set), `DJANGO_LOG_LEVEL` (level for `django.*` loggers),
  `TRACKING_LOG_FILE` (path for the tracking-handler fallback, default
  `/openedx/data/logs/tracking_logs.log`).
- Tests: `DJANGO_SETTINGS_MODULE = "ol_openedx_logging.settings.test"` (set in
  `pyproject.toml`) — this plugin is self-contained enough to unit-test without
  edx-platform.

## Notes
- `configure_structlog()` is idempotent (guarded by a module-level `_configured` flag)
  so it's safe under Django autoreload; Celery workers must pass `force=True` since
  Celery resets logging after Django's setup.
- Has no hard runtime dependency on `opentelemetry` — trace-context injection silently
  no-ops if the package isn't installed (imported once at module load, not lazily, to
  avoid a logging re-entrancy loop from `DeprecationWarning`s during import).
- Deliberately mirrors `mitol.observability.logging` but is self-contained (no
  dependency on `mitol-django-observability`).
- Exception rendering uses `structlog`'s `ExceptionDictTransformer` with
  `show_locals=False` to avoid leaking local variable values into logs.
