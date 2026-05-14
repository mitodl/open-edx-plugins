"""Tests for the Canvas integration MFE endpoints."""

from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import patch

from common.djangoapps.student.roles import CourseInstructorRole
from common.djangoapps.student.tests.factories import UserFactory
from django.test import RequestFactory, override_settings
from lms.djangoapps.instructor_task.models import InstructorTask
from ol_openedx_canvas_integration.views import list_canvas_tasks
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory
import re
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from ol_openedx_canvas_integration.constants import COURSE_KEY_ID_EMPTY

from ol_openedx_canvas_integration import views

HTTP_OK = 200


@skip_unless_lms
@override_settings(BULK_EMAIL_DEFAULT_RETRY_DELAY=10, BULK_EMAIL_MAX_RETRIES=5)
class ListCanvasTasksViewTests(ModuleStoreTestCase):
    """Tests for the list_canvas_tasks endpoint.

    The view function is invoked directly via RequestFactory (rather than the
    Django test client) so the test does not depend on the full session/auth
    middleware stack.
    """

    def setUp(self):
        super().setUp()
        self.course = CourseFactory.create()
        self.course_id = str(self.course.id)
        self.instructor = UserFactory.create()
        CourseInstructorRole(self.course.id).add_users(self.instructor)
        self.factory = RequestFactory()

    def _get(self, user):
        request = self.factory.get(
            f"/courses/{self.course_id}/canvas/api/list_canvas_tasks"
        )
        request.user = user
        return list_canvas_tasks(request, course_id=self.course_id)

    def _create_canvas_task(self, task_type, results):
        task = InstructorTask.create(
            course_id=self.course.id,
            task_type=task_type,
            task_key="",
            task_input={},
            requester=self.instructor,
        )
        task.task_state = "SUCCESS"
        task.task_output = json.dumps({"results": results, "duration_ms": 1000})
        task.save()
        return task

    def test_requires_course_permission(self):
        """A user without instructor permission gets a 403."""
        assert self._get(UserFactory.create()).status_code == HTTPStatus.FORBIDDEN

    def test_returns_empty_list_when_no_tasks(self):
        response = self._get(self.instructor)
        assert response.status_code == HTTPStatus.OK
        assert json.loads(response.content) == {"tasks": []}

    def test_lists_canvas_tasks(self):
        """Canvas tasks are returned, serialized with the expected fields."""
        self._create_canvas_task(
            "push_edx_grades_to_canvas", {"grades": 3, "assignments": 2}
        )

        response = self._get(self.instructor)

        assert response.status_code == HTTPStatus.OK
        tasks = json.loads(response.content)["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_type"] == "push_edx_grades_to_canvas"
        assert tasks[0]["requester"] == self.instructor.username

    def test_canvas_message_uses_plugin_formatter(self):
        """The task message is produced by the plugin's own formatter, so the
        endpoint does not depend on the edx-platform cherry-pick."""
        self._create_canvas_task(
            "sync_canvas_enrollments", {"grades": 0, "assignments": 0}
        )

        with patch(
            "ol_openedx_canvas_integration.views.get_task_output_formatted_message",
            return_value="CANVAS SENTINEL MESSAGE",
        ):
            response = self._get(self.instructor)

        assert response.status_code == HTTPStatus.OK
        tasks = json.loads(response.content)["tasks"]
        assert tasks[0]["task_message"] == "CANVAS SENTINEL MESSAGE"


def _unwrap_callable(func):
    """Unwrap decorators, including wrappers that don't set __wrapped__."""
    current = func
    seen = set()

    while id(current) not in seen:
        seen.add(id(current))

        wrapped = getattr(current, "__wrapped__", None)
        if callable(wrapped):
            current = wrapped
            continue

        closure = getattr(current, "__closure__", None) or ()
        freevars = getattr(current, "__code__", None)
        freevars = getattr(freevars, "co_freevars", ())

        next_func = None
        for name, cell in zip(freevars, closure):
            try:
                value = cell.cell_contents
            except ValueError:
                continue
            if name in {"func", "view_func", "wrapped", "callback"} and callable(value):
                next_func = value
                break

        if callable(next_func):
            current = next_func
            continue

        break

    return current


def _call_view(view_func, request, course_id):
    return _unwrap_callable(view_func)(request, course_id=course_id)


def _stub_canvas_client_factory(stub_client):
    def _factory(**_kwargs):
        return stub_client

    return _factory


class StubResponse:
    """Simple response object stub used by view tests."""

    def __init__(self, status_code=200, data=None):
        """Initialize response fields used by assertions."""
        self.status_code = status_code
        self.data = data or {}


@pytest.mark.parametrize(
    ("has_user", "has_allowed", "is_enrolled_val", "expected"),
    [
        pytest.param(
            False,
            False,
            False,
            {"exists_in_edx": False, "enrolled_in_edx": False, "allowed_in_edx": False},
            id="no_user_no_allowed",
        ),
        pytest.param(
            True,
            False,
            False,
            {"exists_in_edx": True, "enrolled_in_edx": False, "allowed_in_edx": False},
            id="user_exists_not_enrolled",
        ),
        pytest.param(
            True,
            False,
            True,
            {"exists_in_edx": True, "enrolled_in_edx": True, "allowed_in_edx": False},
            id="user_enrolled",
        ),
        pytest.param(
            False,
            True,
            False,
            {"exists_in_edx": False, "enrolled_in_edx": False, "allowed_in_edx": True},
            id="allowed_enrollment",
        ),
    ],
)
def test_get_edx_enrollment_data(has_user, has_allowed, is_enrolled_val, expected):
    """Test that _get_edx_enrollment_data returns correct flags for all combos."""
    email = "test@example.com"
    course_key = "course-v1:MITx+Demo+2026"
    user = SimpleNamespace(id=100, email=email) if has_user else None
    allowed = (
        SimpleNamespace(email=email, course_id=course_key) if has_allowed else None
    )

    original_user_objects = views.User.objects
    original_allowed_objects = views.CourseEnrollmentAllowed.objects
    original_is_enrolled = views.CourseEnrollment.is_enrolled

    views.User.objects = SimpleNamespace(
        filter=lambda **_kwargs: SimpleNamespace(first=lambda: user)
    )
    views.CourseEnrollmentAllowed.objects = SimpleNamespace(
        filter=lambda **_kwargs: SimpleNamespace(first=lambda: allowed)
    )
    views.CourseEnrollment.is_enrolled = lambda _u, _ck: is_enrolled_val

    try:
        result = views._get_edx_enrollment_data(email, course_key)  # noqa: SLF001
        assert result == expected
    finally:
        views.User.objects = original_user_objects
        views.CourseEnrollmentAllowed.objects = original_allowed_objects
        views.CourseEnrollment.is_enrolled = original_is_enrolled


@pytest.mark.parametrize(
    "view_func",
    [
        pytest.param(views.list_canvas_enrollments, id="list_canvas_enrollments"),
        pytest.param(views.list_canvas_assignments, id="list_canvas_assignments"),
        pytest.param(views.list_canvas_grades, id="list_canvas_grades"),
    ],
)
def test_list_view_raises_when_no_course_id(view_func):
    """Test that list views raise when course_id is empty, before any processing."""
    request = MagicMock()

    with pytest.raises(Exception, match=re.escape(COURSE_KEY_ID_EMPTY)):
        _call_view(view_func, request, course_id="")


def test_list_canvas_enrollments_raises_when_no_canvas_course_id(monkeypatch):
    """Test that list canvas enrollments raises when no canvas course id."""
    request = MagicMock()
    course_key = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return None

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)

    error_message = f"No canvas_course_id set for course: {course_key}"
    with pytest.raises(Exception, match=re.escape(error_message)):
        _call_view(views.list_canvas_enrollments, request, course_id=course_key)


def test_list_canvas_enrollments_success(monkeypatch):
    """Test that list canvas enrollments success."""
    request = MagicMock()
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    enrollment_dict = {
        "user1@example.com": {"id": 101},
        "user2@example.com": {"id": 102},
    }

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    def mock_user_filter(**_kwargs):
        return SimpleNamespace(first=lambda: None)

    def mock_allowed_filter(**_kwargs):
        return SimpleNamespace(first=lambda: None)

    stub_client = SimpleNamespace(
        list_canvas_enrollments=lambda: enrollment_dict,
    )

    original_user_objects = views.User.objects
    original_allowed_objects = views.CourseEnrollmentAllowed.objects
    original_is_enrolled = views.CourseEnrollment.is_enrolled

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views, "CanvasClient", _stub_canvas_client_factory(stub_client))
    views.User.objects = SimpleNamespace(filter=mock_user_filter)
    views.CourseEnrollmentAllowed.objects = SimpleNamespace(filter=mock_allowed_filter)
    views.CourseEnrollment.is_enrolled = lambda _user, _course_key: False

    try:
        response = _call_view(views.list_canvas_enrollments, request, course_id)

        assert isinstance(response, views.JsonResponse)
        assert response.status_code == HTTP_OK
    finally:
        views.User.objects = original_user_objects
        views.CourseEnrollmentAllowed.objects = original_allowed_objects
        views.CourseEnrollment.is_enrolled = original_is_enrolled


def test_list_canvas_assignments_raises_when_no_canvas_course_id(monkeypatch):
    """Test that list canvas assignments raises when no canvas course id."""
    request = MagicMock()
    course_key = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return None

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)

    error_message = f"No canvas_course_id set for course: {course_key}"
    with pytest.raises(Exception, match=re.escape(error_message)):
        _call_view(views.list_canvas_assignments, request, course_id=course_key)


def test_list_canvas_assignments_success(monkeypatch):
    """Test that list canvas assignments success."""
    request = MagicMock()
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    assignments = [
        {"id": 201, "name": "Assignment 1"},
        {"id": 202, "name": "Assignment 2"},
    ]

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    stub_client = SimpleNamespace(
        list_canvas_assignments=lambda: assignments,
    )

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views, "CanvasClient", _stub_canvas_client_factory(stub_client))

    response = _call_view(views.list_canvas_assignments, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK


def test_list_canvas_grades_raises_when_no_canvas_course_id(monkeypatch):
    """Test that list canvas grades raises when no canvas course id."""
    request = MagicMock()
    request.GET = {"assignment_id": "201"}
    course_key = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return None

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)

    error_message = f"No canvas_course_id set for course {course_key}"
    with pytest.raises(Exception, match=re.escape(error_message)):
        _call_view(views.list_canvas_grades, request, course_id=course_key)


def test_list_canvas_grades_success(monkeypatch):
    """Test that list canvas grades success."""
    request = MagicMock()
    request.GET = {"assignment_id": "201"}
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    grades = [
        {"user_id": 101, "score": 95},
        {"user_id": 102, "score": 87},
    ]

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    stub_client = SimpleNamespace(
        list_canvas_grades=lambda **_kwargs: grades,
    )

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views, "CanvasClient", _stub_canvas_client_factory(stub_client))

    response = _call_view(views.list_canvas_grades, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK


@pytest.mark.parametrize(
    "view_func",
    [
        pytest.param(views.add_canvas_enrollments, id="add_canvas_enrollments"),
        pytest.param(views.push_edx_grades, id="push_edx_grades"),
    ],
)
def test_view_without_course_id_guard_raises_when_no_course_id(monkeypatch, view_func):
    """Test that views without an early course_id guard raise via from_string."""
    request = MagicMock()

    def mock_from_string(_course_id):
        raise Exception(COURSE_KEY_ID_EMPTY)  # noqa: TRY002

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    with pytest.raises(Exception, match=re.escape(COURSE_KEY_ID_EMPTY)):
        _call_view(view_func, request, course_id="")


def test_add_canvas_enrollments_raises_when_no_canvas_course_id(monkeypatch):
    """Test that add canvas enrollments raises when no canvas course id."""
    request = MagicMock()
    request.POST = {"unenroll_current": "true"}
    course_key = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return None

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)

    error_message = f"No canvas_course_id set for course {course_key}"
    with pytest.raises(Exception, match=re.escape(error_message)):
        _call_view(views.add_canvas_enrollments, request, course_id=course_key)


def test_add_canvas_enrollments_success(monkeypatch):
    """Test that add canvas enrollments success."""
    request = MagicMock()
    request.POST = {"unenroll_current": "true"}
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    sync_calls = []

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    def mock_run_sync(**kwargs):
        sync_calls.append(kwargs)

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views.tasks, "run_sync_canvas_enrollments", mock_run_sync)

    response = _call_view(views.add_canvas_enrollments, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK
    assert len(sync_calls) == 1
    assert sync_calls[0] == {
        "request": request,
        "course_key": course_id,
        "canvas_course_id": canvas_course_id,
        "unenroll_current": True,
    }


def test_add_canvas_enrollments_handles_already_running_error(monkeypatch):
    """Test that add canvas enrollments handles already running error."""
    request = MagicMock()
    request.POST = {}
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    def mock_run_sync(**_kwargs):
        msg = "Task already running"
        raise views.AlreadyRunningError(msg)

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views.tasks, "run_sync_canvas_enrollments", mock_run_sync)

    response = _call_view(views.add_canvas_enrollments, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK


def test_push_edx_grades_raises_when_no_canvas_course_id(monkeypatch):
    """Test that push edx grades raises when no canvas course id."""
    request = MagicMock()
    course_key = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return None

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)

    error_message = f"No canvas_course_id set for course: {course_key}"
    with pytest.raises(Exception, match=re.escape(error_message)):
        _call_view(views.push_edx_grades, request, course_id=course_key)


def test_push_edx_grades_success(monkeypatch):
    """Test that push edx grades success."""
    request = MagicMock()
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    push_calls = []

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    def mock_run_push(**kwargs):
        push_calls.append(kwargs)

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views.tasks, "run_push_edx_grades_to_canvas", mock_run_push)

    response = _call_view(views.push_edx_grades, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK
    assert len(push_calls) == 1
    assert push_calls[0] == {"request": request, "course_id": course_id}


def test_push_edx_grades_handles_already_running_error(monkeypatch):
    """Test that push edx grades handles already running error."""
    request = MagicMock()
    course_id = "course-v1:MITx+Demo+2026"
    course_key = course_id
    course = SimpleNamespace(id=course_id)
    canvas_course_id = 5555

    def mock_from_string(_course_id):
        return course_key

    def mock_get_course(_course_key):
        return course

    def mock_get_canvas_id(_course):
        return canvas_course_id

    def mock_run_push(**_kwargs):
        msg = "Task already running"
        raise views.AlreadyRunningError(msg)

    monkeypatch.setattr(views.CourseLocator, "from_string", mock_from_string)
    monkeypatch.setattr(views, "get_course_by_id", mock_get_course)
    monkeypatch.setattr(views, "get_canvas_course_id", mock_get_canvas_id)
    monkeypatch.setattr(views.tasks, "run_push_edx_grades_to_canvas", mock_run_push)

    response = _call_view(views.push_edx_grades, request, course_id)

    assert isinstance(response, views.JsonResponse)
    assert response.status_code == HTTP_OK
