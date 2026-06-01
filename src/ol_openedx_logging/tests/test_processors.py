"""Tests for ol_openedx_logging.processors."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from ol_openedx_logging.processors import inject_k8s_context, inject_otel_context

# ---------------------------------------------------------------------------
# inject_k8s_context
# ---------------------------------------------------------------------------


class TestInjectK8sContext:
    """Tests for inject_k8s_context."""

    def _call(self, event_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        event_dict = event_dict or {}
        return inject_k8s_context(None, "info", event_dict)

    def test_no_k8s_env_vars(self, monkeypatch):
        """No K8s env vars → event dict is unchanged."""
        monkeypatch.delenv("KUBERNETES_POD_NAME", raising=False)
        monkeypatch.delenv("KUBERNETES_NAMESPACE", raising=False)
        monkeypatch.delenv("KUBERNETES_NODE_NAME", raising=False)

        # Patch the module-level dict since it's precomputed at import time.
        with patch("ol_openedx_logging.processors._K8S_CONTEXT", {}):
            result = self._call({"event": "hello"})

        assert result == {"event": "hello"}

    def test_k8s_env_vars_injected(self):
        """K8s context dict is merged into the event dict."""
        k8s = {
            "pod_name": "lms-abc123",
            "namespace": "mitx-production",
            "node_name": "node-1",
        }
        with patch("ol_openedx_logging.processors._K8S_CONTEXT", k8s):
            result = self._call({"event": "hello"})

        assert result["pod_name"] == "lms-abc123"
        assert result["namespace"] == "mitx-production"
        assert result["node_name"] == "node-1"
        assert result["event"] == "hello"

    def test_existing_keys_not_overwritten(self):
        """Existing keys are overwritten (dict.update semantics)."""
        k8s = {"pod_name": "new-pod"}
        with patch("ol_openedx_logging.processors._K8S_CONTEXT", k8s):
            result = self._call({"event": "x", "pod_name": "old-pod"})
        assert result["pod_name"] == "new-pod"


# ---------------------------------------------------------------------------
# inject_otel_context
# ---------------------------------------------------------------------------


class TestInjectOtelContext:
    """Tests for inject_otel_context."""

    def _call(self, event_dict: dict[str, Any] | None = None) -> dict[str, Any]:
        event_dict = event_dict or {}
        return inject_otel_context(None, "info", event_dict)

    def test_already_has_trace_and_span(self):
        """Skips injection when trace_id and span_id already present."""
        event = {"trace_id": "aaa", "span_id": "bbb", "event": "x"}
        result = self._call(event)
        assert result["trace_id"] == "aaa"
        assert result["span_id"] == "bbb"

    def test_otel_import_error_returns_unchanged(self):
        """Returns event dict unchanged when opentelemetry is not installed."""
        import builtins  # noqa: PLC0415

        real_import = builtins.__import__
        err_msg = "not installed"

        def mock_import(name, *args, **kwargs):
            if name.startswith("opentelemetry"):
                raise ImportError(err_msg)
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            result = self._call({"event": "hello"})

        assert result == {"event": "hello"}

    def test_no_active_span_returns_unchanged(self):
        """Returns event dict unchanged when there is no active OTel span."""
        try:
            from opentelemetry import trace  # noqa: PLC0415
            from opentelemetry.trace import (  # noqa: PLC0415
                NonRecordingSpan,
                SpanContext,
            )
        except ImportError:
            pytest.skip("opentelemetry not installed")

        invalid_ctx = SpanContext(
            trace_id=0,
            span_id=0,
            is_remote=False,
        )
        mock_span = NonRecordingSpan(invalid_ctx)
        with patch.object(trace, "get_current_span", return_value=mock_span):
            result = self._call({"event": "hello"})

        assert "trace_id" not in result
        assert "span_id" not in result

    def test_active_span_injects_context(self):
        """Injects trace_id and span_id when there is a valid recording span."""
        try:
            from opentelemetry import trace  # noqa: PLC0415
        except ImportError:
            pytest.skip("opentelemetry not installed")

        mock_ctx = MagicMock()
        mock_ctx.is_valid = True
        mock_ctx.trace_id = 0xABCD1234ABCD1234ABCD1234ABCD1234
        mock_ctx.span_id = 0x1234ABCD1234ABCD

        mock_span = MagicMock()
        mock_span.get_span_context.return_value = mock_ctx
        mock_span.is_recording.return_value = True

        with patch.object(trace, "get_current_span", return_value=mock_span):
            result = self._call({"event": "hello"})

        assert "trace_id" in result
        assert "span_id" in result
        assert isinstance(result["trace_id"], str)
        assert isinstance(result["span_id"], str)
