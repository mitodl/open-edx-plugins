"""Celery integration helpers for ol_openedx_logging.

This module provides a ``setup_celery_logging`` function that re-applies the
structlog configuration inside Celery worker processes.

Celery fires a ``setup_logging`` signal during worker boot, giving
applications the opportunity to override its default logging setup.  Without
a receiver Celery installs its own basic logging config; with one it defers
to the application entirely.

The plugin wires this up automatically in ``AppConfig.ready()`` by connecting
to the signal — no changes are required to the edx-platform ``celery.py``.

Usage (manual, if auto-wiring is not desired)
---------------------------------------------
In the edx-platform ``openedx/core/lib/celery/__init__.py`` or a site
celery module::

    from celery.signals import setup_logging
    from ol_openedx_logging.celery import setup_celery_logging

    @setup_logging.connect
    def on_setup_logging(**kwargs):
        setup_celery_logging(**kwargs)
"""

from __future__ import annotations


def setup_celery_logging(**_kwargs) -> None:
    """Configure structlog inside a Celery worker process.

    Celery can reset the logging configuration between Django setup and the
    ``setup_logging`` signal, so we force structlog to re-apply its config
    here via ``force=True``.

    ``_kwargs`` accepts (and ignores) the keyword arguments Celery passes to
    ``setup_logging`` receivers: ``loglevel``, ``logfile``, ``format``, and
    ``colorize``.  Log level and debug mode are intentionally read from the
    ``LOG_LEVEL`` / ``EDXAPP_LOG_LEVEL`` env vars and ``settings.DEBUG``,
    matching the web-process behaviour.
    """
    from ol_openedx_logging.logging import configure_structlog  # noqa: PLC0415

    configure_structlog(force=True)
