"""AppConfig for ol_openedx_logging.

Registers this plugin with the LMS and CMS and wires up structlog
configuration both for Django web processes (via ``ready()``) and for
Celery worker processes (via the ``setup_logging`` signal receiver).
"""

from django.apps import AppConfig


class EdxLoggingLMS(AppConfig):
    """Open edX LMS plugin that replaces the default logging stack with structlog."""

    name = "ol_openedx_logging"
    verbose_name = "Structured logging for Open edX (LMS)"
    plugin_app = {
        "settings_config": {
            "lms.djangoapp": {
                "production": {"relative_path": "settings.production"},
            }
        }
    }

    def ready(self) -> None:
        """Configure structlog and wire up Celery worker logging."""
        from ol_openedx_logging.logging import configure_structlog  # noqa: PLC0415

        configure_structlog()
        _connect_celery_signal()


class EdxLoggingCMS(AppConfig):
    """Open edX CMS plugin that replaces the default logging stack with structlog."""

    name = "ol_openedx_logging"
    verbose_name = "Structured logging for Open edX (CMS)"
    plugin_app = {
        "settings_config": {
            "cms.djangoapp": {
                "production": {"relative_path": "settings.production"},
            }
        }
    }

    def ready(self) -> None:
        """Configure structlog and wire up Celery worker logging."""
        from ol_openedx_logging.logging import configure_structlog  # noqa: PLC0415

        configure_structlog()
        _connect_celery_signal()


def _connect_celery_signal() -> None:
    """Connect the ``setup_logging`` Celery signal if Celery is installed.

    Celery is an optional dependency — the web process runs fine without it.
    The signal receiver calls ``configure_structlog(force=True)`` so that
    structlog is re-applied after Celery resets the logging configuration
    in worker processes.
    """
    try:
        from celery.signals import setup_logging  # noqa: PLC0415

        from ol_openedx_logging.celery import setup_celery_logging  # noqa: PLC0415
    except ImportError:
        return

    setup_logging.connect(setup_celery_logging)
