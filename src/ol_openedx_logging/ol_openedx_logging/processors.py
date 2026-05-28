"""Custom structlog processors for context injection.

These processors are used in the structlog pipeline to enrich log records
with OpenTelemetry trace context and Kubernetes pod metadata.
"""

from __future__ import annotations

import os
from typing import Any

# Precompute K8s context dict at import time — values don't change during
# process lifetime.  A single dict.update() is faster than multiple writes.
_K8S_CONTEXT: dict[str, str] = {
    k: v
    for k, v in {
        "pod_name": os.environ.get("KUBERNETES_POD_NAME"),
        "namespace": os.environ.get("KUBERNETES_NAMESPACE"),
        "node_name": os.environ.get("KUBERNETES_NODE_NAME"),
    }.items()
    if v
}


def inject_otel_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace context into the structlog event dict.

    Skips injection when ``opentelemetry`` is not installed (soft dependency),
    when trace/span IDs are already present, or when there is no active
    recording span.

    ``opentelemetry`` is imported lazily inside the function so that the plugin
    can be installed in environments without the OTel SDK.  Python caches
    modules after the first import, so the per-call overhead is negligible.

    Performance notes:
    - Fast-path on ``ImportError`` (otel not installed).
    - Skips when trace_id/span_id already present (bound via contextvars).
    - Checks ``is_valid`` before ``is_recording`` for the fastest invalid-
      context short-circuit.
    """
    if "trace_id" in event_dict and "span_id" in event_dict:
        return event_dict

    try:
        from opentelemetry import trace  # noqa: PLC0415
        from opentelemetry.trace.span import (  # noqa: PLC0415
            format_span_id,
            format_trace_id,
        )
    except ImportError:
        return event_dict

    span = trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return event_dict
    if not span.is_recording():
        return event_dict

    event_dict["trace_id"] = format_trace_id(ctx.trace_id)
    event_dict["span_id"] = format_span_id(ctx.span_id)
    return event_dict


def inject_k8s_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject Kubernetes pod metadata into the structlog event dict.

    Values are read once at import time from well-known Downward API env vars
    (``KUBERNETES_POD_NAME``, ``KUBERNETES_NAMESPACE``, ``KUBERNETES_NODE_NAME``)
    and merged into every log record with a single ``dict.update()`` call.
    When none of the env vars are set (e.g., local development) the function
    is a cheap no-op.
    """
    if _K8S_CONTEXT:
        event_dict.update(_K8S_CONTEXT)
    return event_dict
