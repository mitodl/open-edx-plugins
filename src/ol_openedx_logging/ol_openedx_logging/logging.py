"""Structlog configuration for the Open edX platform.

This module configures structlog and routes stdlib logging through it.
It is intended to be called from the plugin's ``AppConfig.ready()`` hook,
which runs after Django has applied the base ``LOGGING`` setting.

The implementation mirrors ``mitol.observability.logging`` but is
self-contained so that this plugin has no runtime dependency on
``mitol-django-observability``.  Context-injection processors live in
:mod:`ol_openedx_logging.processors`.

Environment variables
---------------------
``LOG_LEVEL``
    Root log level (default: ``INFO``).  Takes precedence over
    ``EDXAPP_LOG_LEVEL``.
``EDXAPP_LOG_LEVEL``
    edX-style log level env token; used as fallback when ``LOG_LEVEL`` is
    not set.
``DJANGO_LOG_LEVEL``
    Level for ``django.*`` loggers (default: ``INFO``).
"""

from __future__ import annotations

import logging
import logging.config
import os
from typing import Any

import structlog
from structlog.tracebacks import ExceptionDictTransformer

from ol_openedx_logging.processors import inject_k8s_context, inject_otel_context

# Idempotency guard — prevents double-configuration under Django autoreload.
_configured = False

# Structured exception renderer for production JSON logs.
# ``show_locals=False`` prevents local variable values from leaking into log
# output (security + size). ``max_frames=20`` keeps payloads reasonable.
# The dict format is preferred over a flat string because Loki/Grafana can
# index individual fields (exc_type, exc_value, frames[].filename, etc.).
_EXCEPTION_RENDERER = structlog.processors.ExceptionRenderer(
    ExceptionDictTransformer(
        show_locals=False,
        max_frames=20,
    )
)


def _get_log_level() -> str:
    """Return root log level from env, preferring LOG_LEVEL over EDXAPP_LOG_LEVEL."""
    return (
        os.environ.get("LOG_LEVEL") or os.environ.get("EDXAPP_LOG_LEVEL") or "INFO"
    ).upper()


def _get_django_log_level() -> str:
    """Return the level to apply to ``django.*`` loggers."""
    return os.environ.get("DJANGO_LOG_LEVEL", "INFO").upper()


def _shared_processors() -> list[Any]:
    """Return processors used in both dev and prod chains."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.stdlib.PositionalArgumentsFormatter(),
        inject_otel_context,
        inject_k8s_context,
        structlog.processors.StackInfoRenderer(),
    ]


def configure_structlog(*, debug: bool | None = None, force: bool = False) -> None:
    """Configure structlog and route stdlib logging through it.

    This function is idempotent — safe to call multiple times (e.g., under
    Django autoreload or in test setups).  In Celery worker processes pass
    ``force=True`` to ensure structlog is reconfigured after Celery resets
    logging.

    The function reads the existing ``settings.LOGGING`` to extract any edX
    platform-specific handlers and loggers (most importantly the ``tracking``
    handler used for event tracking) so they are preserved in the new config.

    Args:
        debug: Override debug-mode detection.  If ``None``, reads from
            ``django.conf.settings.DEBUG``.
        force: Re-run configuration even if already configured.  Use in
            Celery worker processes via a ``worker_process_init`` signal.
    """
    global _configured  # noqa: PLW0603
    if _configured and not force:
        return
    _configured = True

    from django.conf import settings  # noqa: PLC0415

    if debug is None:
        debug = getattr(settings, "DEBUG", False)

    log_level = _get_log_level()
    django_log_level = _get_django_log_level()

    shared = _shared_processors()

    if debug:
        # ConsoleRenderer handles exc_info tuples natively (including rich /
        # better-exceptions rendering when those libraries are installed).
        # set_exc_info ensures exc_info=True is resolved to the actual tuple
        # at call-site so that ConsoleRenderer can render it later.
        exc_processor: Any = structlog.dev.set_exc_info
        renderer: Any = structlog.dev.ConsoleRenderer(colors=True)
        formatter_processors: list[Any] = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ]
    else:
        # _EXCEPTION_RENDERER converts exc_info (tuple, Exception, or True)
        # into a structured ``exception`` dict before JSONRenderer serialises
        # the event.  It must appear in BOTH the structlog pipeline (for
        # structlog-native records) AND in ProcessorFormatter.processors
        # (for foreign stdlib records, e.g. Django / third-party loggers,
        # where exc_info is injected by ProcessorFormatter from LogRecord).
        exc_processor = _EXCEPTION_RENDERER
        renderer = structlog.processors.JSONRenderer()
        formatter_processors = [
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _EXCEPTION_RENDERER,
            renderer,
        ]

    # structlog pipeline: ends with wrap_for_formatter so that stdlib records
    # routed through ProcessorFormatter share the same pre-chain processing.
    structlog.configure(
        processors=[
            *shared,
            exc_processor,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # ProcessorFormatter handles both structlog records (wrapped above) and
    # foreign stdlib records (via foreign_pre_chain).  The final processor
    # must be a renderer that returns a string.
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=formatter_processors,
        foreign_pre_chain=shared,
    )

    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    # Preserve edX-specific handlers, formatters, and loggers from the existing
    # LOGGING configuration.  The ``tracking`` handler/logger is critical —
    # it routes event-tracking data to a separate syslog facility and must not
    # be lost.  We also carry over any formatters the preserved handlers
    # reference (e.g. edX's ``raw`` formatter used by ``tracking``).
    existing_logging = getattr(settings, "LOGGING", {})
    extra_handlers: dict[str, Any] = {}
    extra_formatters: dict[str, Any] = {}
    extra_loggers: dict[str, Any] = {}

    existing_formatters = existing_logging.get("formatters", {})

    tracking_handler = existing_logging.get("handlers", {}).get("tracking")
    if tracking_handler:
        extra_handlers["tracking"] = tracking_handler
        # Carry over the formatter referenced by this handler, if any.
        fmt_name = tracking_handler.get("formatter")
        if fmt_name and fmt_name in existing_formatters:
            extra_formatters[fmt_name] = existing_formatters[fmt_name]

    tracking_logger = existing_logging.get("loggers", {}).get("tracking")
    if tracking_logger:
        extra_loggers["tracking"] = tracking_logger

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                **extra_formatters,
            },
            "handlers": {
                "console": {
                    "()": lambda: handler,
                },
                **extra_handlers,
            },
            "loggers": {
                "django": {
                    "handlers": ["console"],
                    "level": django_log_level,
                    "propagate": False,
                },
                "django.request": {
                    "handlers": ["console"],
                    "level": django_log_level,
                    "propagate": False,
                },
                "boto3": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "botocore": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                "opensearch": {
                    "handlers": ["console"],
                    "level": "ERROR",
                    "propagate": False,
                },
                # django-structlog context propagation middleware
                "django_structlog": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                # Celery worker and task loggers
                "celery": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "celery.task": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                "celery.worker": {
                    "handlers": ["console"],
                    "level": log_level,
                    "propagate": False,
                },
                **extra_loggers,
            },
            "root": {"handlers": ["console"], "level": log_level},
        }
    )


def reset_configuration() -> None:
    """Reset configuration state for testing purposes.

    This allows tests to re-run ``configure_structlog()`` with different
    settings.  Should only be used in test code.
    """
    global _configured  # noqa: PLW0603
    _configured = False
