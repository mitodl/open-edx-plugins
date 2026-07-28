from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from ol_openedx_canvas_integration import task_helpers


class FakeQuerySet(list):
    """List-backed queryset stub with a small Django-like API surface."""

    def order_by(self, field_name):
        """Return items sorted by field name, supporting leading '-' for desc."""
        reverse = field_name.startswith("-")
        key_name = field_name.lstrip("-")
        return FakeQuerySet(
            sorted(self, key=lambda item: getattr(item, key_name), reverse=reverse)
        )

    def __or__(self, other):
        """Return combined queryset contents."""
        return FakeQuerySet([*self, *other])

    def distinct(self):
        """Deduplicate items by id while preserving order."""
        seen_ids = set()
        distinct_items = []
        for item in self:
            if item.id not in seen_ids:
                seen_ids.add(item.id)
                distinct_items.append(item)
        return FakeQuerySet(distinct_items)

    def __getitem__(self, index):
        """Return sliced results as FakeQuerySet and scalar indexes as-is."""
        result = super().__getitem__(index)
        return FakeQuerySet(result) if isinstance(index, slice) else result


class StubTaskProgress:
    """Collect task progress updates for assertions."""

    def __init__(self, action_name, num_reports, start_time):
        """Initialize task progress fields and call capture list."""
        self.action_name = action_name
        self.num_reports = num_reports
        self.start_time = start_time
        self.update_calls = []

    def update_task_state(self, **kwargs):
        """Record and return update payloads like the production helper."""
        self.update_calls.append(kwargs)
        return {"status": "updated", "kwargs": kwargs}


class StubApiModule:
    """API module stub that records enrollment and grade sync calls."""

    def __init__(self):
        """Initialize call capture containers."""
        self.sync_enrollments_calls = []
        self.push_grades_calls = []

    def sync_canvas_enrollments(self, course_key, canvas_course_id, unenroll_current):
        """Record sync_canvas_enrollments arguments."""
        self.sync_enrollments_calls.append(
            {
                "course_key": course_key,
                "canvas_course_id": canvas_course_id,
                "unenroll_current": unenroll_current,
            }
        )

    def push_edx_grades_to_canvas(self, course):
        """Record push_edx_grades_to_canvas calls and return canned output."""
        self.push_grades_calls.append({"course": course})
        return {"assignment-1": "grade-1"}, {"assignment-2": "grade-2"}


def test_sync_canvas_enrollments_calls_api_and_updates_task(monkeypatch):
    """Test that sync canvas enrollments calls api and updates task."""
    stub_api = StubApiModule()
    stub_progress = StubTaskProgress("sync", 1, 0)

    monkeypatch.setattr(task_helpers, "api", stub_api)
    monkeypatch.setattr(
        task_helpers,
        "TaskProgress",
        lambda _action, _num, _start: stub_progress,
    )

    task_input = {
        "course_key": "course-v1:MITx+Demo+2026",
        "canvas_course_id": 7777,
        "unenroll_current": True,
    }

    result = task_helpers.sync_canvas_enrollments(
        _xmodule_instance_args={},
        _entry_id=1,
        course_id="course-v1:MITx+Demo+2026",
        task_input=task_input,
        action_name="sync_canvas_enrollments",
    )

    assert stub_api.sync_enrollments_calls == [
        {
            "course_key": "course-v1:MITx+Demo+2026",
            "canvas_course_id": 7777,
            "unenroll_current": True,
        }
    ]
    assert stub_progress.update_calls == [{"extra_meta": {"step": "Done"}}]
    assert result == {"status": "updated", "kwargs": {"extra_meta": {"step": "Done"}}}


def test_push_edx_grades_to_canvas_calls_api_and_updates_task(monkeypatch):
    """Test that push edx grades to canvas calls api and updates task."""
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    stub_api = StubApiModule()
    stub_progress = StubTaskProgress("push_grades", 1, 0)

    monkeypatch.setattr(task_helpers, "api", stub_api)
    monkeypatch.setattr(
        task_helpers,
        "TaskProgress",
        lambda _action, _num, _start: stub_progress,
    )
    monkeypatch.setattr(task_helpers, "get_course_by_id", lambda _course_id: course)

    result = task_helpers.push_edx_grades_to_canvas(
        _xmodule_instance_args={},
        _entry_id=2,
        course_id="course-v1:MITx+Demo+2026",
        task_input={},
        action_name="push_edx_grades_to_canvas",
    )

    assert stub_api.push_grades_calls == [{"course": course}]
    assert stub_progress.update_calls == [
        {
            "extra_meta": {
                "step": "Done",
                "results": {"grades": 1, "assignments": 1},
            }
        }
    ]
    assert result == {
        "status": "updated",
        "kwargs": {
            "extra_meta": {
                "step": "Done",
                "results": {"grades": 1, "assignments": 1},
            }
        },
    }


def test_get_filtered_instructor_tasks_filters_by_type_and_date(monkeypatch):
    """Test that get filtered instructor tasks filters by type and date."""
    course_id = "course-v1:MITx+Demo+2026"
    user = SimpleNamespace(id=1)
    now = datetime.now(UTC)

    running_task = SimpleNamespace(id=10, task_type="grade_download")
    canvas_task_1 = SimpleNamespace(
        id=20,
        course_id=course_id,
        task_type="sync_canvas_enrollments",
        updated=now - timedelta(hours=1),
        requester=user,
    )
    canvas_task_2 = SimpleNamespace(
        id=21,
        course_id=course_id,
        task_type="push_edx_grades_to_canvas",
        updated=now - timedelta(days=1),
        requester=user,
    )
    old_task = SimpleNamespace(
        id=22,
        course_id=course_id,
        task_type="sync_canvas_enrollments",
        updated=now - timedelta(days=3),
        requester=user,
    )

    running_tasks_qs = FakeQuerySet([running_task])
    all_instructor_tasks = [canvas_task_1, canvas_task_2, old_task]

    def mock_get_running_tasks(cid):
        return running_tasks_qs if cid == course_id else FakeQuerySet()

    def mock_instructor_task_filter(**filters):
        result = all_instructor_tasks
        if "task_type__in" in filters:
            result = [t for t in result if t.task_type in filters["task_type__in"]]
        if "updated__lte" in filters:
            result = [t for t in result if t.updated <= filters["updated__lte"]]
        if "updated__gte" in filters:
            result = [t for t in result if t.updated >= filters["updated__gte"]]
        if "requester" in filters:
            result = [t for t in result if t.requester == filters["requester"]]
        return FakeQuerySet(result)

    task_types = [
        "sync_canvas_enrollments",
        "push_edx_grades_to_canvas",
    ]
    monkeypatch.setattr(task_helpers, "CANVAS_TASK_TYPES", task_types)
    monkeypatch.setattr(
        task_helpers, "get_running_instructor_tasks", mock_get_running_tasks
    )
    monkeypatch.setattr(
        task_helpers.InstructorTask.objects,
        "filter",
        mock_instructor_task_filter,
    )

    result = task_helpers.get_filtered_instructor_tasks(course_id, user)

    assert canvas_task_1 in result
    assert canvas_task_2 in result
    assert old_task not in result
    assert running_task in result
