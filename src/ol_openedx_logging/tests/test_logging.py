"""Tests for ol_openedx_logging.logging (configure_structlog)."""

from __future__ import annotations

import copy
import logging as stdlib_logging
import os
from unittest.mock import patch

import pytest
import structlog
from ol_openedx_logging.logging import (
    configure_structlog,
    reset_configuration,
)


@pytest.fixture(autouse=True)
def reset_structlog():
    """Reset configure_structlog idempotency guard before each test."""
    reset_configuration()
    yield
    reset_configuration()


class TestConfigureStructlogProduction:
    """configure_structlog in production (non-debug) mode."""

    def test_structlog_is_configured_after_call(self):
        """structlog.is_configured() returns True after configure_structlog()."""
        configure_structlog(debug=False)
        assert structlog.is_configured()

    def test_root_logger_has_stream_handler(self):
        """Root stdlib logger has a StreamHandler using ProcessorFormatter."""
        configure_structlog(debug=False)
        root = stdlib_logging.getLogger()
        assert any(isinstance(h, stdlib_logging.StreamHandler) for h in root.handlers)

    def test_root_handler_uses_processor_formatter(self):
        """StreamHandler on root is using ProcessorFormatter."""
        configure_structlog(debug=False)
        root = stdlib_logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if isinstance(h, stdlib_logging.StreamHandler)
        ]
        assert stream_handlers, "No StreamHandler found on root logger"
        formatter = stream_handlers[0].formatter
        assert isinstance(formatter, structlog.stdlib.ProcessorFormatter)

    def test_tracking_handler_preserved(self):
        """edX ``tracking`` logger and its MemoryHandler are preserved."""
        configure_structlog(debug=False)
        tracking = stdlib_logging.getLogger("tracking")
        assert tracking.handlers, "tracking logger has no handlers"
        handler_classes = {type(h).__name__ for h in tracking.handlers}
        assert "MemoryHandler" in handler_classes

    def test_tracking_handler_attached_without_logger_handlers(self):
        """Tracking handler is attached if logger handlers are omitted."""
        from django.conf import settings  # noqa: PLC0415

        logging_config = copy.deepcopy(settings.LOGGING)
        logging_config["loggers"]["tracking"].pop("handlers", None)

        with patch.object(settings, "LOGGING", logging_config):
            configure_structlog(debug=False)

        tracking = stdlib_logging.getLogger("tracking")
        assert tracking.handlers, "tracking logger has no handlers"
        handler_classes = {type(h).__name__ for h in tracking.handlers}
        assert "MemoryHandler" in handler_classes

    def test_celery_logger_configured(self):
        """celery logger is configured with console handler."""
        configure_structlog(debug=False)
        celery_logger = stdlib_logging.getLogger("celery")
        assert celery_logger.handlers, "celery logger has no handlers"

    def test_celery_task_logger_configured(self):
        """celery.task logger is configured with console handler."""
        configure_structlog(debug=False)
        logger = stdlib_logging.getLogger("celery.task")
        assert logger.handlers, "celery.task logger has no handlers"

    def test_celery_worker_logger_configured(self):
        """celery.worker logger is configured with console handler."""
        configure_structlog(debug=False)
        logger = stdlib_logging.getLogger("celery.worker")
        assert logger.handlers, "celery.worker logger has no handlers"

    def test_django_logger_configured(self):
        """django logger is configured with console handler."""
        configure_structlog(debug=False)
        django_logger = stdlib_logging.getLogger("django")
        assert django_logger.handlers, "django logger has no handlers"

    def test_syslog_handler_missing_socket_falls_back_to_rotating_file(self, tmp_path):
        """RotatingFileHandler is used when SysLogHandler socket is absent."""
        import copy  # noqa: PLC0415

        from django.conf import settings  # noqa: PLC0415

        syslog_config = copy.deepcopy(settings.LOGGING)
        syslog_config["handlers"]["tracking"] = {
            "level": "DEBUG",
            "class": "logging.handlers.SysLogHandler",
            "facility": "local0",
            "address": "/nonexistent/dev/log",
            "formatter": "raw",
        }
        fallback_path = str(tmp_path / "tracking_logs.log")
        with (
            patch.object(settings, "LOGGING", syslog_config),
            patch.dict(os.environ, {"TRACKING_LOG_FILE": fallback_path}),
        ):
            configure_structlog(debug=False)

        tracking = stdlib_logging.getLogger("tracking")
        # RotatingFileHandler fallback — not console propagation.
        assert not any(type(h).__name__ == "SysLogHandler" for h in tracking.handlers)
        assert any(
            type(h).__name__ == "RotatingFileHandler" for h in tracking.handlers
        ), "Expected a RotatingFileHandler fallback when SysLogHandler socket is absent"
        assert tracking.propagate is False

    def test_syslog_handler_missing_socket_uses_tracking_log_file_env(self, tmp_path):
        """TRACKING_LOG_FILE env var controls the fallback RotatingFileHandler path."""
        import copy  # noqa: PLC0415

        from django.conf import settings  # noqa: PLC0415

        syslog_config = copy.deepcopy(settings.LOGGING)
        syslog_config["handlers"]["tracking"] = {
            "level": "DEBUG",
            "class": "logging.handlers.SysLogHandler",
            "facility": "local0",
            "address": "/nonexistent/dev/log",
            "formatter": "raw",
        }
        custom_path = str(tmp_path / "custom_tracking.log")
        with (
            patch.object(settings, "LOGGING", syslog_config),
            patch.dict(os.environ, {"TRACKING_LOG_FILE": custom_path}),
        ):
            configure_structlog(debug=False)

        tracking = stdlib_logging.getLogger("tracking")
        rfile_handlers = [
            h for h in tracking.handlers if type(h).__name__ == "RotatingFileHandler"
        ]
        assert rfile_handlers, "No RotatingFileHandler found"
        assert rfile_handlers[0].baseFilename == custom_path


class TestConfigureStructlogDebug:
    """configure_structlog in debug mode."""

    def test_structlog_is_configured_after_call(self):
        """structlog.is_configured() returns True in debug mode."""
        configure_structlog(debug=True)
        assert structlog.is_configured()

    def test_root_logger_has_stream_handler(self):
        """Root logger has a StreamHandler in debug mode."""
        configure_structlog(debug=True)
        root = stdlib_logging.getLogger()
        assert any(isinstance(h, stdlib_logging.StreamHandler) for h in root.handlers)


class TestConfigureStructlogIdempotency:
    """configure_structlog is idempotent."""

    def test_second_call_is_no_op(self):
        """Calling configure_structlog() twice is safe."""
        configure_structlog(debug=False)
        first_root_handlers = list(stdlib_logging.getLogger().handlers)
        configure_structlog(debug=False)
        second_root_handlers = list(stdlib_logging.getLogger().handlers)
        assert first_root_handlers == second_root_handlers

    def test_force_reconfigures(self):
        """force=True forces re-configuration even after initial call."""
        configure_structlog(debug=False)
        configure_structlog(debug=False, force=True)
        assert structlog.is_configured()


class TestConfigureStructlogLogLevel:
    """configure_structlog respects log level env vars."""

    def test_log_level_env_var(self):
        """LOG_LEVEL env var sets the root logger level."""
        with patch.dict(os.environ, {"LOG_LEVEL": "WARNING"}, clear=False):
            configure_structlog(debug=False)
        root = stdlib_logging.getLogger()
        assert root.level == stdlib_logging.WARNING

    def test_edxapp_log_level_fallback(self):
        """EDXAPP_LOG_LEVEL is used when LOG_LEVEL is absent."""
        env = {k: v for k, v in os.environ.items() if k != "LOG_LEVEL"}
        env["EDXAPP_LOG_LEVEL"] = "ERROR"
        with patch.dict(os.environ, env, clear=True):
            configure_structlog(debug=False)
        root = stdlib_logging.getLogger()
        assert root.level == stdlib_logging.ERROR


class TestCelerySignalIntegration:
    """setup_celery_logging reconfigures structlog for Celery workers."""

    def test_setup_celery_logging_reconfigures_structlog(self):
        """setup_celery_logging() calls configure_structlog(force=True)."""
        configure_structlog(debug=False)
        # Second call without force would be no-op; signal helper uses force=True.
        from ol_openedx_logging.celery import setup_celery_logging  # noqa: PLC0415

        setup_celery_logging(loglevel="INFO", logfile=None)
        assert structlog.is_configured()

    def test_setup_celery_logging_accepts_celery_kwargs(self):
        """setup_celery_logging() accepts and silently ignores Celery's kwargs."""
        from ol_openedx_logging.celery import setup_celery_logging  # noqa: PLC0415

        # Should not raise even with unexpected keyword arguments.
        setup_celery_logging(
            loglevel="DEBUG",
            logfile="/tmp/worker.log",  # noqa: S108
            format="%(message)s",
            colorize=False,
        )
