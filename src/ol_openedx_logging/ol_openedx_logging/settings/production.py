"""Production settings for ol_openedx_logging.

This module is loaded by the Open edX plugin settings machinery before
``django.setup()`` runs.  Its sole responsibility is to translate edX
environment tokens into the canonical ``LOG_LEVEL`` environment variable so
that ``configure_structlog()`` (called later in ``AppConfig.ready()``) picks
up the correct log level without needing direct access to ``ENV_TOKENS``.

The old JSON-file handler and ``RotatingFileHandler`` configuration has been
removed.  Structured JSON logs are now written to stdout/stderr by structlog's
``JSONRenderer`` and should be captured by the container / log-shipper layer.
"""

from __future__ import annotations

import os
from typing import Any


def plugin_settings(edx_settings: Any) -> None:
    """Translate edX log-level tokens into the canonical ``LOG_LEVEL`` env var.

    If the operator has set ``EDXAPP_LOG_LEVEL`` via ``ENV_TOKENS`` (or the
    environment directly) and ``LOG_LEVEL`` is not already set, we forward the
    value so that ``configure_structlog()`` honours it without any edX-specific
    knowledge.
    """
    env_tokens: dict[str, Any] = getattr(edx_settings, "ENV_TOKENS", {})

    edxapp_log_level: str = (
        env_tokens.get("EDXAPP_LOG_LEVEL") or os.environ.get("EDXAPP_LOG_LEVEL") or ""
    ).upper()

    if edxapp_log_level and not os.environ.get("LOG_LEVEL"):
        os.environ["LOG_LEVEL"] = edxapp_log_level
