from __future__ import annotations

from types import SimpleNamespace

import pytest

from ol_openedx_canvas_integration import handlers


class StubSyncTask:
    """Capture queued task invocations for handler tests."""

    def __init__(self):
        """Initialize storage for delay and apply_async calls."""
        self.delay_calls = []
        self.apply_async_calls = []

    def delay(self, *args):
        """Record a delayed task invocation."""
        self.delay_calls.append(args)

    def apply_async(self, **kwargs):
        """Record a scheduled task invocation."""
        self.apply_async_calls.append(kwargs)


def test_handle_xblock_publised_event_queues_sync(monkeypatch):
    """Test that handle xblock publised event queues sync."""
    course_key = "course-v1:MITx+Demo+2026"
    xblock_info = SimpleNamespace(
        usage_key=SimpleNamespace(course_key=course_key),
        block_type="problem",
    )
    stub_task = StubSyncTask()

    monkeypatch.setattr(handlers, "sync_course_assignments_with_canvas", stub_task)

    handlers.handle_xblock_publised_event(
        signal="signal", sender="sender", xblock_info=xblock_info, metadata={}
    )

    assert stub_task.delay_calls == [(course_key,)]
    assert stub_task.apply_async_calls == []


@pytest.mark.parametrize("block_type", ["chapter", "sequential"])
def test_handle_xblock_deleted_event_queues_delayed_sync(monkeypatch, block_type):
    """Test that handle xblock deleted event queues delayed sync."""
    course_key = "course-v1:MITx+Demo+2026"
    xblock_info = SimpleNamespace(
        usage_key=SimpleNamespace(course_key=course_key),
        block_type=block_type,
    )
    stub_task = StubSyncTask()

    monkeypatch.setattr(handlers, "sync_course_assignments_with_canvas", stub_task)

    handlers.handle_xblock_deleted_event(
        signal="signal", sender="sender", xblock_info=xblock_info, metadata={}
    )

    assert stub_task.delay_calls == []
    assert stub_task.apply_async_calls == [
        {
            "args": [course_key],
            "countdown": 10,
        }
    ]


def test_handle_xblock_deleted_event_skips_non_assignment_blocks(monkeypatch):
    """Test that handle xblock deleted event skips non assignment blocks."""
    xblock_info = SimpleNamespace(
        usage_key=SimpleNamespace(course_key="course-v1:MITx+Demo+2026"),
        block_type="problem",
    )
    stub_task = StubSyncTask()

    monkeypatch.setattr(handlers, "sync_course_assignments_with_canvas", stub_task)

    handlers.handle_xblock_deleted_event(
        signal="signal", sender="sender", xblock_info=xblock_info, metadata={}
    )

    assert stub_task.delay_calls == []
    assert stub_task.apply_async_calls == []
