"""Tests for Canvas integration tasks"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import requests
from common.djangoapps.student.tests.factories import UserFactory
from django.test import TestCase, override_settings
from lms.djangoapps.grades.models import PersistentSubsectionGrade
from ol_openedx_canvas_integration.tasks import _sync_user_grade_with_canvas
from opaque_keys.edx.keys import CourseKey, UsageKey
from openedx.core.djangolib.testing.utils import skip_unless_lms

from ol_openedx_canvas_integration import tasks


@override_settings(BULK_EMAIL_DEFAULT_RETRY_DELAY=10, BULK_EMAIL_MAX_RETRIES=5)
@patch("ol_openedx_canvas_integration.tasks.submit_task", MagicMock(return_value=None))
@patch(
    "ol_openedx_canvas_integration.tasks.get_course_by_id",
    MagicMock(return_value=MagicMock()),
)
@skip_unless_lms
class TestSyncUserGradeWithCanvas(TestCase):
    """Tests for _sync_user_grade_with_canvas task"""

    def setUp(self):
        """Setup test data"""
        self.grade_id = 123
        self.course_id = CourseKey.from_string("course-v1:org+course+run")
        self.usage_key = UsageKey.from_string(
            "block-v1:org+course+run+type@sequential+block@subsection"
        )
        self.canvas_course_id = "canvas-123"
        self.email = "student@example.com"
        self.canvas_user_id = 456
        self.canvas_assignment_id = 789
        self.user = UserFactory.create(
            username="student",
            email="student@example.com",
        )
        self.grade_instance = PersistentSubsectionGrade.update_or_create_grade(
            user_id=self.user.id,
            id=self.grade_id,
            course_id=self.course_id,
            usage_key=self.usage_key,
            earned_all=6.0,
            possible_all=12.0,
            earned_graded=6.0,
            possible_graded=8.0,
            visible_blocks=[],
            first_attempted=datetime.now(tz=UTC),
        )
        # Mock Course
        self.course = MagicMock()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch("ol_openedx_canvas_integration.tasks.TASK_LOG")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_success(
        self,
        mock_task_log,
        mock_get_grades,
        mock_client_class,
    ):
        """Test successful grade sync to Canvas"""
        mock_client = mock_client_class.return_value
        # The graded assignment is linked to canvas
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        # The user is linked to a Canvas user
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(
            status_code=requests.codes.ok
        )

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {self.usage_key: {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_called_once()

        mock_task_log.error.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value=None),
    )
    def test_no_canvas_id(
        self,
        mock_client_class,
    ):
        """Test that grades are not synced if course has no linked canvas id"""
        _sync_user_grade_with_canvas(self.grade_id)

        mock_client_class.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_assignment_not_synced(
        self,
        mock_client_class,
    ):
        """Test that assignments that are not synced to Canvas are not updated."""
        mock_client = mock_client_class.return_value
        # There are assignment synced to Canvas, but not the one being graded
        mock_client.get_canvas_assignments.return_value = {
            "dummy-key": {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_assignment_past_due_date(
        self,
        mock_client_class,
    ):
        """Test that grades are not synced for assignments past due date"""
        mock_client = mock_client_class.return_value
        # Assignment is synced to Canvas, but past due date
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": str(datetime.now(tz=UTC) - timedelta(days=1)),
            }
        }

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_no_canvas_user_id(
        self,
        mock_client_class,
    ):
        """Test that grades are not synced if user is not linked to a Canvas user"""
        mock_client = mock_client_class.return_value
        # The assignment is linked to Canvas ...
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        # ... but the user is not linked to a Canvas user
        mock_client.get_student_id_by_email.return_value = None

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_key_error(
        self,
        mock_get_grades,
        mock_client_class,
    ):
        """Test successful grade sync to Canvas"""
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(
            status_code=requests.codes.ok
        )

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {"dummy-key": {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_not_called()

    @patch("ol_openedx_canvas_integration.tasks.CanvasClient")
    @patch("ol_openedx_canvas_integration.tasks.get_subsection_user_grades")
    @patch("ol_openedx_canvas_integration.tasks.TASK_LOG")
    @patch(
        "ol_openedx_canvas_integration.tasks.get_canvas_course_id",
        MagicMock(return_value="canvas-123"),
    )
    def test_sync_fail_code(
        self,
        mock_task_log,
        mock_get_grades,
        mock_client_class,
    ):
        """Test that grades are not synced if the Canvas API returns an error"""
        mock_client = mock_client_class.return_value
        mock_client.get_canvas_assignments.return_value = {
            str(self.usage_key): {
                "id": self.canvas_assignment_id,
                "due_at": "",
            }
        }
        mock_client.get_student_id_by_email.return_value = self.canvas_user_id
        mock_client.update_assignment_grades.return_value = MagicMock(status_code=502)

        grade_obj = MagicMock()
        grade_obj.percent_graded = 0.85
        mock_get_grades.return_value = {self.usage_key: {self.user: grade_obj}}

        _sync_user_grade_with_canvas(self.grade_id)

        mock_client.update_assignment_grades.assert_called_once()

        mock_task_log.error.assert_called_once()


class StubSubmitTask:
    """Callable submit_task stub that records invocation arguments."""

    def __init__(self):
        """Initialize submit call capture list."""
        self.calls = []

    def __call__(self, *args, **_kwargs):
        """Record positional submit_task arguments by semantic key."""
        self.calls.append(
            {
                "request": args[0],
                "task_type": args[1],
                "task_class": args[2],
                "course_id": args[3],
                "task_input": args[4],
                "task_key": args[5],
            }
        )
        return {"task_id": "test-task-id"}


class HashableUser:
    """Minimal user stub with stable hashing for dict key usage."""

    def __init__(self, user_id, email):
        """Initialize id and email fields used by task logic."""
        self.id = user_id
        self.email = email

    def __hash__(self):
        """Hash by id and email for deterministic key behavior."""
        return hash((self.id, self.email))

    def __eq__(self, other):
        """Compare HashableUser instances by id and email."""
        return (
            isinstance(other, HashableUser)
            and self.id == other.id
            and self.email == other.email
        )


def _stub_canvas_client_factory(stub_client):
    def _factory(**_kwargs):
        return stub_client

    return _factory


def test_run_sync_canvas_enrollments_submits_task(monkeypatch):
    """Test that run sync canvas enrollments submits task."""
    request = SimpleNamespace()
    course_key = "course-v1:MITx+Demo+2026"
    canvas_course_id = 9999
    unenroll_current = True

    stub_submit = StubSubmitTask()
    monkeypatch.setattr(tasks, "submit_task", stub_submit)

    result = tasks.run_sync_canvas_enrollments(
        request, course_key, canvas_course_id, unenroll_current
    )

    assert len(stub_submit.calls) == 1
    call = stub_submit.calls[0]
    assert call["request"] is request
    assert call["task_type"] == "sync_canvas_enrollments"
    assert call["task_class"] == tasks.sync_canvas_enrollments_task
    assert call["course_id"] == course_key
    assert call["task_input"] == {
        "course_key": course_key,
        "canvas_course_id": canvas_course_id,
        "unenroll_current": unenroll_current,
    }
    assert result == {"task_id": "test-task-id"}


def test_run_push_edx_grades_to_canvas_submits_task(monkeypatch):
    """Test that run push edx grades to canvas submits task."""
    request = SimpleNamespace()
    course_id = "course-v1:MITx+Demo+2026"

    stub_submit = StubSubmitTask()
    monkeypatch.setattr(tasks, "submit_task", stub_submit)

    result = tasks.run_push_edx_grades_to_canvas(request, course_id)

    assert len(stub_submit.calls) == 1
    call = stub_submit.calls[0]
    assert call["request"] is request
    assert call["task_type"] == "push_edx_grades_to_canvas"
    assert call["task_class"] == tasks.push_edx_grades_to_canvas_task
    assert call["course_id"] == course_id
    assert call["task_input"] == {"course_key": str(course_id)}
    assert result == {"task_id": "test-task-id"}


def test_sync_user_grade_with_canvas_skips_when_no_canvas_course_id(monkeypatch):
    """Test that sync user grade with canvas skips when no canvas course id."""
    grade_instance = SimpleNamespace(
        id=1,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: None)

    result = tasks.sync_user_grade_with_canvas(1)

    assert result is None


def test_sync_user_grade_with_canvas_skips_when_assignment_not_synced(monkeypatch):
    """Test that sync user grade with canvas skips when assignment not synced."""
    grade_instance = SimpleNamespace(
        id=2,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
        full_usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
        usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    stub_client = SimpleNamespace(
        get_canvas_assignments=dict,
    )

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: 5555)
    monkeypatch.setattr(tasks, "CanvasClient", _stub_canvas_client_factory(stub_client))

    result = tasks.sync_user_grade_with_canvas(2)

    assert result is None


def test_sync_user_grade_with_canvas_skips_when_user_not_in_canvas(monkeypatch):
    """Test that sync user grade with canvas skips when user not in canvas."""
    grade_instance = SimpleNamespace(
        id=3,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
        full_usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
        usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    stub_client = SimpleNamespace(
        get_canvas_assignments=lambda: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {"id": 201}
        },
        get_student_id_by_email=lambda _email: None,
    )
    openedx_user = HashableUser(100, "learner@example.com")

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: 5555)
    monkeypatch.setattr(tasks, "CanvasClient", _stub_canvas_client_factory(stub_client))
    monkeypatch.setattr(
        tasks.USER_MODEL.objects,
        "get",
        lambda **_kwargs: openedx_user,
    )

    result = tasks.sync_user_grade_with_canvas(3)

    assert result is None


def test_sync_user_grade_with_canvas_skips_when_grade_not_found(monkeypatch):
    """Test that sync user grade with canvas skips when grade not found."""
    grade_instance = SimpleNamespace(
        id=4,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
        full_usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
        usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    stub_client = SimpleNamespace(
        get_canvas_assignments=lambda: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {"id": 201}
        },
        get_student_id_by_email=lambda _email: 300,
    )
    openedx_user = HashableUser(100, "learner@example.com")

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: 5555)
    monkeypatch.setattr(tasks, "CanvasClient", _stub_canvas_client_factory(stub_client))
    monkeypatch.setattr(
        tasks.USER_MODEL.objects,
        "get",
        lambda **_kwargs: openedx_user,
    )
    monkeypatch.setattr(
        tasks,
        "get_subsection_user_grades",
        lambda _course, _usage_key, _user: {},
    )

    result = tasks.sync_user_grade_with_canvas(4)

    assert result is None


def test_sync_user_grade_with_canvas_success(monkeypatch):
    """Test that sync user grade with canvas success."""
    grade_instance = SimpleNamespace(
        id=5,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
        full_usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
        usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    grade_obj = SimpleNamespace(percent_graded=0.95)
    update_response = SimpleNamespace(status_code=200)
    stub_client = SimpleNamespace(
        get_canvas_assignments=lambda: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {"id": 201}
        },
        get_student_id_by_email=lambda _email: 300,
        update_assignment_grades=lambda _assign_id, _payload: update_response,
    )
    openedx_user = HashableUser(100, "learner@example.com")

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: 5555)
    monkeypatch.setattr(tasks, "CanvasClient", _stub_canvas_client_factory(stub_client))
    monkeypatch.setattr(
        tasks.USER_MODEL.objects,
        "get",
        lambda **_kwargs: openedx_user,
    )
    monkeypatch.setattr(
        tasks,
        "get_subsection_user_grades",
        lambda _course, _usage_key, _user: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {openedx_user: grade_obj}
        },
    )

    result = tasks.sync_user_grade_with_canvas(5)

    assert result is None


def test_sync_user_grade_with_canvas_handles_api_error(monkeypatch):
    """Test that sync user grade with canvas handles api error."""
    grade_instance = SimpleNamespace(
        id=6,
        course_id="course-v1:MITx+Demo+2026",
        user_id=100,
        full_usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
        usage_key="block-v1:MITx+Demo+type@sequential+block@hw1",
    )
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    grade_obj = SimpleNamespace(percent_graded=0.85)
    update_response = SimpleNamespace(status_code=500)
    stub_client = SimpleNamespace(
        get_canvas_assignments=lambda: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {"id": 201}
        },
        get_student_id_by_email=lambda _email: 300,
        update_assignment_grades=lambda _assign_id, _payload: update_response,
    )
    openedx_user = HashableUser(100, "learner@example.com")

    monkeypatch.setattr(
        tasks.PersistentSubsectionGrade.objects,
        "get",
        lambda **_kwargs: grade_instance,
    )
    monkeypatch.setattr(tasks, "get_course_by_id", lambda _cid: course)
    monkeypatch.setattr(tasks, "get_canvas_course_id", lambda _c: 5555)
    monkeypatch.setattr(tasks, "CanvasClient", _stub_canvas_client_factory(stub_client))
    monkeypatch.setattr(
        tasks.USER_MODEL.objects,
        "get",
        lambda **_kwargs: openedx_user,
    )
    monkeypatch.setattr(
        tasks,
        "get_subsection_user_grades",
        lambda _course, _usage_key, _user: {
            "block-v1:MITx+Demo+type@sequential+block@hw1": {openedx_user: grade_obj}
        },
    )

    result = tasks.sync_user_grade_with_canvas(6)

    assert result is None
