"""Sentry configuration for Open edX (ol_openedx_sentry plugin).

The plugin initializes the Sentry SDK from ``ENV_TOKENS`` when a DSN is
configured and installs a ``before_send`` filter that drops events matching
operator-configured exception types or message regexes.

Design notes
------------
* ``before_send`` is *fail-open*: any unexpected error is logged and the event
  is returned unfiltered, so a bug in the filter can never silently blackhole
  error reporting.
* Ignored exception classes and message regexes are resolved/compiled once at
  init time (not per event), so a bad import path or invalid regex is reported
  once and skipped rather than raising inside ``before_send``.
* The default ``LoggingIntegration`` is configured explicitly with
  ``event_level=None`` so that stdlib/structlog log records become breadcrumbs
  only, never standalone Sentry issues.  Uncaught exceptions are still captured
  by the Django integration.
* Postgres ``DETAIL:`` lines are truncated out of exception values and log
  messages before send.  They echo the offending row verbatim -- learner name,
  email, external UUID -- and no SDK privacy option covers exception text.
* OpenTelemetry ``trace_id``/``span_id`` are stamped onto every event as tags
  using the same formatting as ``ol_openedx_logging`` so Sentry issues and the
  structured logs in Loki correlate on identical values.  ``opentelemetry`` is
  a soft dependency; this module deliberately does not import
  ``ol_openedx_logging``.
"""

from __future__ import annotations

import builtins
import importlib
import logging
import re
from functools import partial
from typing import Any

import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration

logger = logging.getLogger(__name__)

# Soft OpenTelemetry import — mirrors ``ol_openedx_logging.processors`` so the
# plugins stay independent.  Names are always defined so tests can patch them
# regardless of whether opentelemetry is installed.
try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace.span import format_span_id as _format_span_id
    from opentelemetry.trace.span import format_trace_id as _format_trace_id

    _OTEL_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised via patching in tests
    _otel_trace = None
    _format_span_id = None
    _format_trace_id = None
    _OTEL_AVAILABLE = False


def _load_exception_class(import_specifier: str) -> type[BaseException] | None:
    """Resolve a dotted import path (or builtin name) to an exception class.

    :param import_specifier: Full import path for an exception class, e.g.
        ``'ValueError'`` or ``'requests.exceptions.HTTPError'``.

    :returns: The exception class, or ``None`` (with a warning logged) when the
        path cannot be resolved or does not name a ``BaseException`` subclass.
        Returning ``None`` instead of raising ensures a config typo cannot
        blackhole error reporting.
    """
    try:
        module_name, _, class_name = import_specifier.rpartition(".")
        if not module_name:
            candidate = getattr(builtins, import_specifier, None)
        else:
            candidate = getattr(importlib.import_module(module_name), class_name, None)
    except (ImportError, AttributeError, ValueError):
        logger.warning(
            "ol_openedx_sentry: could not import ignored exception class %r; "
            "skipping it",
            import_specifier,
        )
        return None
    if isinstance(candidate, type) and issubclass(candidate, BaseException):
        return candidate
    logger.warning(
        "ol_openedx_sentry: ignored exception class %r did not resolve to a "
        "BaseException subclass; skipping it",
        import_specifier,
    )
    return None


def _compile_patterns(ignored_messages: Any) -> list[re.Pattern[str]]:
    """Compile the ignored-message regexes once at init.

    Each entry may be a string (a single pattern) or a list/tuple of strings
    (each element becomes its own pattern).  The list/tuple form tolerates
    deployment configs that express a message as adjacent string fragments,
    which serialize to a YAML sequence.  Non-string fragments and invalid
    regexes are logged and skipped rather than raising.
    """
    # A bare string is a common misconfiguration (the token expects a list):
    # iterating it directly would compile one regex per character and drop
    # unrelated events, so treat it as a single entry.
    if isinstance(ignored_messages, (str, bytes)):
        ignored_messages = [ignored_messages]
    patterns: list[re.Pattern[str]] = []
    for entry in ignored_messages or []:
        fragments = entry if isinstance(entry, (list, tuple)) else [entry]
        for fragment in fragments:
            if not isinstance(fragment, str):
                logger.warning(
                    "ol_openedx_sentry: ignored-message pattern %r is not a "
                    "string; skipping",
                    fragment,
                )
                continue
            try:
                patterns.append(re.compile(fragment))
            except re.error:
                logger.warning(
                    "ol_openedx_sentry: invalid ignored-message regex %r; skipping",
                    fragment,
                )
    return patterns


def _event_messages(event: dict[str, Any], exception_value: object) -> list[str]:
    """Collect candidate message strings to match ignored-message regexes.

    Covers exception events (``str(exc)``) and log-only events (the
    ``logentry`` message/formatted string and any top-level ``message``), so the
    message filter applies whether or not the event carries an exception.
    """
    candidates: list[str] = []
    if exception_value:
        candidates.append(str(exception_value))
    logentry = event.get("logentry") or {}
    for key in ("formatted", "message"):
        value = logentry.get(key)
        if isinstance(value, str) and value:
            candidates.append(value)
    top_message = event.get("message")
    if isinstance(top_message, str) and top_message:
        candidates.append(top_message)
    return candidates


# Postgres appends a DETAIL line to constraint violations that echoes the whole
# offending row verbatim -- on a users table that is the learner's name, email
# and external UUID.  psycopg surfaces it as part of str(exc), so it reaches
# Sentry inside the exception value and the log message, where no SDK privacy
# setting applies: send_default_pii governs user/cookie/header capture and
# max_request_body_size governs request bodies, neither of which touches the
# exception text.  Measured on mitxonline MITXONLINE-6PK, where a SCIM PATCH
# IntegrityError reproduced a learner email address three times per event across
# 46,764 occurrences.
_PG_DETAIL_MARKER = "\nDETAIL:"
_PG_DETAIL_REPLACEMENT = "\nDETAIL:  [scrubbed by ol_openedx_sentry]"


def _scrub_pg_detail(text: str) -> str:
    """Truncate a Postgres error string at its ``DETAIL:`` line.

    Keeps the primary message, which is what identifies the failure, and drops
    the row echo that follows it.  Also removes any HINT/CONTEXT that Postgres
    appends after DETAIL -- those are diagnostic only and can quote row data
    too.
    """
    index = text.find(_PG_DETAIL_MARKER)
    if index == -1:
        return text
    return text[:index] + _PG_DETAIL_REPLACEMENT


def _scrub_pg_details(event: dict[str, Any]) -> dict[str, Any]:
    """Apply :func:`_scrub_pg_detail` everywhere an error string lands.

    Covers exception values, the ``logentry`` message/formatted pair, and the
    legacy top-level ``message``, so the scrub holds whether the event arrived
    as an uncaught exception or via ``logger.exception``.
    """
    for entry in (event.get("exception") or {}).get("values") or []:
        value = entry.get("value")
        if isinstance(value, str):
            entry["value"] = _scrub_pg_detail(value)
    logentry = event.get("logentry")
    if isinstance(logentry, dict):
        for key in ("formatted", "message"):
            value = logentry.get(key)
            if isinstance(value, str):
                logentry[key] = _scrub_pg_detail(value)
    top_message = event.get("message")
    if isinstance(top_message, str):
        event["message"] = _scrub_pg_detail(top_message)
    return event


def _tag_otel_context(event: dict[str, Any]) -> dict[str, Any]:
    """Stamp the active OTel ``trace_id``/``span_id`` onto the event as tags.

    Uses the same formatting as ``ol_openedx_logging`` so Sentry issues and the
    structured logs shipped to Loki can be joined on identical values.  A no-op
    when opentelemetry is unavailable or there is no valid recording span.
    """
    if not _OTEL_AVAILABLE:
        return event
    span = _otel_trace.get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid or not span.is_recording():
        return event
    tags = event.setdefault("tags", {})
    tags.setdefault("trace_id", _format_trace_id(ctx.trace_id))
    tags.setdefault("span_id", _format_span_id(ctx.span_id))
    return event


def sentry_event_filter(
    event: dict[str, Any],
    hint: dict[str, Any],
    *,
    ignored_classes: tuple[type[BaseException], ...] = (),
    ignored_patterns: tuple[re.Pattern[str], ...] = (),
) -> dict[str, Any] | None:
    """``before_send`` hook: drop ignored events, else tag and pass through.

    Drops the event (returns ``None``) when the raised exception is a subclass
    of an ignored type, or when any candidate message matches an ignored regex.
    Otherwise scrubs Postgres ``DETAIL`` row echoes, stamps OTel trace context,
    and returns the event.

    Fail-open: any unexpected error is logged and the event is returned, so a
    bug here can never silently drop error reporting.  The scrub runs first so
    that the fail-open path still returns a scrubbed event.

    :param event: Sentry event payload.
    :param hint: Sentry event hint (may contain ``exc_info``).
        https://docs.sentry.io/platforms/python/configuration/filtering/hints/
    :param ignored_classes: Exception classes to drop, resolved at init.
    :param ignored_patterns: Compiled message regexes to drop, built at init.
    :returns: The (possibly tagged) event, or ``None`` to drop it.
    """
    try:
        # Scrub before anything else can raise: the fail-open handler below
        # returns this same dict, and a privacy control must not fail open.
        _scrub_pg_details(event)
        exception_info = hint.get("exc_info")
        exception_value: object = ""
        if exception_info:
            exception_class, exception_value = exception_info[0], exception_info[1]
            if (
                ignored_classes
                and isinstance(exception_class, type)
                and issubclass(exception_class, ignored_classes)
            ):
                return None
        messages = _event_messages(event, exception_value)
        for pattern in ignored_patterns:
            if any(pattern.search(message) for message in messages):
                return None
        return _tag_otel_context(event)
    except Exception:
        logger.warning(
            "ol_openedx_sentry: sentry_event_filter raised; passing the event "
            "through unfiltered",
            exc_info=True,
        )
        return event


def _coerce_log_event_level(value: Any) -> int | None:
    """Map a ``SENTRY_LOG_EVENT_LEVEL`` token to a logging level, or ``None``.

    ``None`` (the default) disables turning log records into Sentry events.
    Accepts an int level or a level name (e.g. ``"ERROR"``).  An unknown name
    is logged and treated as ``None``.
    """
    if value is None:
        return None
    if isinstance(value, int):
        return value
    level = logging.getLevelName(str(value).upper())
    if isinstance(level, int):
        return level
    logger.warning(
        "ol_openedx_sentry: unknown SENTRY_LOG_EVENT_LEVEL %r; disabling log-as-event",
        value,
    )
    return None


def _load_env_tokens(app_settings) -> dict[str, Any]:
    """Return the ``ENV_TOKENS`` mapping, or an empty dict when absent."""
    return getattr(app_settings, "ENV_TOKENS", {})


def plugin_settings(app_settings):
    """Initialize the Sentry SDK when a DSN is configured in ``ENV_TOKENS``."""
    env_tokens = _load_env_tokens(app_settings)
    sentry_dsn = env_tokens.get("SENTRY_DSN")
    if not sentry_dsn:
        return

    class_specs = env_tokens.get("SENTRY_IGNORED_EXCEPTION_CLASSES", [])
    # Guard the same bare-string misconfiguration as _compile_patterns: a plain
    # string would otherwise be iterated character by character.
    if isinstance(class_specs, str):
        class_specs = [class_specs]
    ignored_classes = tuple(
        cls
        for cls in (_load_exception_class(spec) for spec in class_specs)
        if cls is not None
    )
    ignored_patterns = tuple(
        _compile_patterns(env_tokens.get("SENTRY_IGNORED_EXCEPTION_MESSAGES", []))
    )
    log_event_level = _coerce_log_event_level(env_tokens.get("SENTRY_LOG_EVENT_LEVEL"))

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=env_tokens.get("SENTRY_ENVIRONMENT"),
        # Performance tracing is off by default; operators opt in per deployment.
        traces_sample_rate=env_tokens.get("SENTRY_TRACES_SAMPLE_RATE", 0),
        # PII (user id/username/IP) is opt-in — FERPA-sensitive by default.
        send_default_pii=env_tokens.get("SENTRY_SEND_DEFAULT_PII", False),
        release=env_tokens.get("SENTRY_RELEASE_SPECIFIER"),
        # HTTP request bodies are NOT gated on send_default_pii -- the SDK sets
        # request.data unconditionally and max_request_body_size is the only
        # control (sentry_sdk/integrations/_wsgi_common.py:61,123).  On Open edX
        # the write endpoints that actually error are xblock handler POSTs, i.e.
        # graded problem submissions, and those are routinely under the 1,000
        # bytes that "small" still admits.  Default to "never" here; operators
        # can widen it per deployment.
        max_request_body_size=env_tokens.get(
            "SENTRY_SEND_HTTP_REQUEST_BODIES", "never"
        ),
        # Explicit LoggingIntegration: log records are breadcrumbs only
        # (event_level=None) so structlog/stdlib logs don't become duplicate,
        # noisy Sentry issues.  Uncaught exceptions are still captured by the
        # Django integration.  Operators can restore log-as-event via
        # SENTRY_LOG_EVENT_LEVEL.
        integrations=[
            LoggingIntegration(level=logging.INFO, event_level=log_event_level),
        ],
        before_send=partial(
            sentry_event_filter,
            ignored_classes=ignored_classes,
            ignored_patterns=ignored_patterns,
        ),
    )
