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


def test_update_grade_in_canvas_triggers_background_task_when_canvas_linked(
    monkeypatch,
):
    """Test that a Canvas-linked course's grade save dispatches the sync task."""
    instance = SimpleNamespace(id=321, course_id="course-v1:MITx+1+2026")
    stub_task = StubSyncUserGradeTask()

    monkeypatch.setattr(receivers, "sync_user_grade_with_canvas", stub_task)
    monkeypatch.setattr(
        receivers, "get_cached_canvas_course_id", lambda _course_id: 12345
    )

    receivers.update_grade_in_canvas(sender="sender", instance=instance, created=False)

    assert stub_task.delay_calls == [(321,)]


def test_update_grade_in_canvas_skips_when_course_not_canvas_linked(monkeypatch):
    """Test that a non-Canvas course's grade save does not dispatch the sync task."""
    instance = SimpleNamespace(id=321, course_id="course-v1:MITx+1+2026")
    stub_task = StubSyncUserGradeTask()

    monkeypatch.setattr(receivers, "sync_user_grade_with_canvas", stub_task)
    monkeypatch.setattr(
        receivers, "get_cached_canvas_course_id", lambda _course_id: None
    )

    receivers.update_grade_in_canvas(sender="sender", instance=instance, created=False)

    assert stub_task.delay_calls == []
