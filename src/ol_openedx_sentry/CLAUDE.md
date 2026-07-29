# CLAUDE.md — ol_openedx_sentry

A Django app plugin that initializes the `sentry-sdk` for Open edX (LMS and CMS) from `ENV_TOKENS`. When no DSN is configured it is a complete no-op, so it's safe to install everywhere and enable per deployment. On top of a bare `sentry_sdk.init`, it adds a fail-open `before_send` filter (drop configured exception types/message regexes), stamps OpenTelemetry `trace_id`/`span_id` onto every event so Sentry issues correlate with `ol_openedx_logging`'s structured logs, and configures `LoggingIntegration` so ordinary log records don't become duplicate Sentry issues.

## Key files
- `ol_openedx_sentry/app.py`: `EdxSentry` AppConfig — registers `settings.sentry` for both `lms.djangoapp` and `cms.djangoapp` (common/production/devstack/test).
- `ol_openedx_sentry/settings/sentry.py`: all the logic — `plugin_settings()` reads `ENV_TOKENS`, resolves ignored exception classes/regexes once at init, and calls `sentry_sdk.init(...)`. Also has `sentry_event_filter` (the `before_send` hook), `_tag_otel_context`, and helpers for coercing config values.
- `tests/test_sentry.py`: unit tests for the filter/init logic, run against `settings/test.py` (a minimal standalone Django config, no edx-platform needed).

## Entry points & settings
- Registers via `lms.djangoapp` / `cms.djangoapp` entry points pointing at `EdxSentry`; `plugin_settings` runs automatically during settings resolution — no manual `INSTALLED_APPS` wiring.
- `DJANGO_SETTINGS_MODULE = ol_openedx_sentry.settings.test` (see `pyproject.toml`) — this plugin's tests run standalone (sqlite, minimal `INSTALLED_APPS`), unlike most plugins in this repo that need a full edx-platform environment.
- Configuration is entirely via `ENV_TOKENS`: `SENTRY_DSN` (master switch — empty/unset means nothing else is read and the SDK never initializes), `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE` (default `0`, i.e. perf tracing off by default), `SENTRY_RELEASE_SPECIFIER`, `SENTRY_SEND_HTTP_REQUEST_BODIES` (default `"small"`), `SENTRY_SEND_DEFAULT_PII` (default `False`, FERPA-sensitive), `SENTRY_IGNORED_EXCEPTION_CLASSES` (dotted paths or builtin names), `SENTRY_IGNORED_EXCEPTION_MESSAGES` (regexes, `re.search`), `SENTRY_LOG_EVENT_LEVEL` (default `None` — log records stay breadcrumbs only).

## Notes
- `before_send` is fail-open by design: any error inside the filter is logged and the original event is returned unfiltered — a filter bug can never blackhole error reporting.
- Ignored classes/regexes are resolved/compiled once at `plugin_settings()` time, not per-event; bad import paths or invalid regexes are logged once and skipped.
- `opentelemetry` is a soft dependency — trace/span tagging silently no-ops if it isn't installed or there's no active recording span. This module deliberately does not import `ol_openedx_logging` to keep the two plugins independent, even though they're designed to correlate.
- Sentry's structured "Logs" feature (`enable_logs`) is intentionally left off — Loki via `ol_openedx_logging` is the system of record for logs; enabling it here would double-ingest.
