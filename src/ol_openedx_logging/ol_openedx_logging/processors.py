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

# Import otel at module load time, not inside the processor.  Lazy imports
# inside a structlog processor are unsafe: importing otel triggers a
# DeprecationWarning from importlib.metadata, that warning re-enters the
# logging system, which calls this processor again before the first import
# completes, producing a recursive error loop.
try:
    from opentelemetry import trace as _otel_trace
    from opentelemetry.trace.span import format_span_id as _format_span_id
    from opentelemetry.trace.span import format_trace_id as _format_trace_id

    _OTEL_AVAILABLE = True
except ImportError:
    _OTEL_AVAILABLE = False


def inject_otel_context(
    _logger: Any,
    _method: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """Inject OpenTelemetry trace context into the structlog event dict.

    Skips injection when ``opentelemetry`` is not installed (soft dependency),
    when trace/span IDs are already present, or when there is no active
    recording span.
    """
    if not _OTEL_AVAILABLE:
        return event_dict

    if "trace_id" in event_dict and "span_id" in event_dict:
        return event_dict

    span = _otel_trace.get_current_span()
    ctx = span.get_span_context()

    if not ctx.is_valid:
        return event_dict
    if not span.is_recording():
        return event_dict

    event_dict["trace_id"] = _format_trace_id(ctx.trace_id)
    event_dict["span_id"] = _format_span_id(ctx.span_id)
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
