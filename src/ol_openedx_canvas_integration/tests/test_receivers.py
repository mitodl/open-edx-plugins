from __future__ import annotations

from types import SimpleNamespace

from ol_openedx_canvas_integration import receivers


class StubSyncUserGradeTask:
    """Task stub that records delay invocations from receivers."""

    def __init__(self):
        """Initialize delay call capture list."""
        self.delay_calls = []

    def delay(self, *args):
        """Record delayed task arguments."""
        self.delay_calls.append(args)


def test_update_grade_in_canvas_triggers_background_task(monkeypatch):
    """Test that update grade in canvas triggers background task."""
    instance = SimpleNamespace(id=321)
    stub_task = StubSyncUserGradeTask()

    monkeypatch.setattr(receivers, "sync_user_grade_with_canvas", stub_task)

    receivers.update_grade_in_canvas(
        sender="sender",
        instance=instance,
        created=False,
    )

    assert stub_task.delay_calls == [(321,)]
