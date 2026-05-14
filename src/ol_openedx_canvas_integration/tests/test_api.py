from __future__ import annotations

import re
from types import SimpleNamespace

import pytest
from ol_openedx_canvas_integration.constants import COURSE_KEY_ID_EMPTY

from ol_openedx_canvas_integration import api


class MockSubsection:
    """Minimal subsection object used for Canvas assignment payload tests."""

    def __init__(self, location: str, display_name: str = "Mock subsection") -> None:
        """Initialize a minimal subsection-like object used by tests."""
        self.location = location
        self.display_name = display_name
        self.fields: dict[str, str] = {}


class HashableUser:
    """Hashable user stub that can be used as a dictionary key."""

    def __init__(self, email: str) -> None:
        """Store an email on a hashable user-like object for dict-key usage."""
        self.email = email

    def __hash__(self) -> int:
        """Hash by email so equivalent email users compare and hash the same."""
        return hash(self.email)

    def __eq__(self, other) -> bool:
        """Return True when another HashableUser has the same email."""
        return isinstance(other, HashableUser) and self.email == other.email


class StubCanvasClient:
    """Canvas client stub that records assignment and grade API interactions."""

    def __init__(self, canvas_course_id):
        """Initialize stub state for Canvas API method assertions."""
        self.canvas_course_id = canvas_course_id
        self.created_assignments = []
        self.updated_assignment_grades = []

    def get_canvas_assignments(self):
        """Return one pre-existing assignment keyed by subsection location."""
        return {
            "block-v1:MITx+course+type@sequential+block@existing": {
                "id": 101,
                "is_published": False,
            }
        }

    def list_canvas_enrollments(self):
        """Return a single enrolled learner mapping of email to Canvas id."""
        return {"learner@example.com": 42}

    def create_canvas_assignment(self, payload):
        """Record and return the assignment creation payload."""
        self.created_assignments.append(payload)
        return {"status": "created", "payload": payload}

    def update_assignment_grades(self, canvas_assignment_id, payload):
        """Record and return an assignment grade update payload."""
        self.updated_assignment_grades.append((canvas_assignment_id, payload))
        return {
            "status": "updated",
            "canvas_assignment_id": canvas_assignment_id,
            "payload": payload,
        }


def _stub_canvas_client_factory(stub_client):
    def _factory(**_kwargs):
        return stub_client

    return _factory


def test_get_enrolled_non_staff_users_filters_out_staff(monkeypatch):
    """Test that only enrolled users without staff access are returned."""
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")
    learner = SimpleNamespace(email="learner@example.com")
    staff = SimpleNamespace(email="staff@example.com")
    ta = SimpleNamespace(email="ta@example.com")
    users = [learner, staff, ta]

    monkeypatch.setattr(
        api.CourseEnrollment.objects,
        "users_enrolled_in",
        lambda _course_id: users,
    )
    monkeypatch.setattr(
        api,
        "has_access",
        lambda user, _role, _course: user.email in {"staff@example.com"},
    )

    result = api.get_enrolled_non_staff_users(course)

    assert result == [learner, ta]


def test_enroll_emails_in_course_creates_new_users_and_enrolls_existing(
    monkeypatch,
):
    """Test that new users get enrollment allowed and existing users are enrolled."""
    course_key = "course-v1:MITx+Demo+2026"
    existing_user = SimpleNamespace(email="existing@example.com")
    enrolled_user = SimpleNamespace(email="enrolled@example.com")
    nonexistent_email = "new@example.com"

    created_allowed = False

    def mock_user_filter(email=None, **_kwargs):
        if email == existing_user.email:
            return SimpleNamespace(first=lambda: existing_user)
        elif email == enrolled_user.email:
            return SimpleNamespace(first=lambda: enrolled_user)
        else:
            return SimpleNamespace(first=lambda: None)

    def mock_get_or_create(**kwargs):
        nonlocal created_allowed
        email = kwargs.get("email")
        if email == nonexistent_email:
            created_allowed = True
            return (SimpleNamespace(email=email), True)
        return (SimpleNamespace(email=email), False)

    def mock_is_enrolled(user, _course_key):
        return user.email == enrolled_user.email

    enrollment_calls = []

    def mock_enroll(user, _course_key):
        enrollment_calls.append(user.email)

    monkeypatch.setattr(api.User.objects, "filter", mock_user_filter)
    monkeypatch.setattr(
        api.CourseEnrollmentAllowed.objects,
        "get_or_create",
        mock_get_or_create,
    )
    monkeypatch.setattr(api.CourseEnrollment, "is_enrolled", mock_is_enrolled)
    monkeypatch.setattr(api.CourseEnrollment, "enroll", mock_enroll)

    result = api.enroll_emails_in_course(
        [existing_user.email, enrolled_user.email, nonexistent_email],
        course_key,
    )

    assert result[existing_user.email] == "Enrolled user in the course"
    assert result[enrolled_user.email] == "User already enrolled"
    assert (
        result[nonexistent_email]
        == "User does not exist - created course enrollment permission"
    )
    assert enrollment_calls == [existing_user.email]


def test_get_subsection_block_user_grades_maps_locator_to_block(monkeypatch):
    """Test that get subsection block user grades maps locator to block."""
    course = object()
    block_1 = MockSubsection("block-1")
    block_2 = MockSubsection("block-2")

    monkeypatch.setattr(
        api,
        "get_subsection_user_grades",
        lambda _course: {
            "block-1": {"student-a": "grade-a"},
            "missing-block": {"student-b": "grade-b"},
        },
    )
    monkeypatch.setattr(
        api,
        "course_graded_items",
        lambda _course: [
            ("Homework", {"subsection_block": block_1}, 1),
            ("Exam", {"subsection_block": block_2}, 2),
        ],
    )

    result = api.get_subsection_block_user_grades(course)

    assert result == {block_1: {"student-a": "grade-a"}}


def test_push_edx_grades_to_canvas_pushes_existing_and_creates_new_assignments(
    monkeypatch,
):
    """Test that existing grades are pushed and missing assignments are created."""
    course = SimpleNamespace(id="course-v1:MITx+course+2026")
    existing_block = MockSubsection(
        "block-v1:MITx+course+type@sequential+block@existing", "Existing assignment"
    )
    new_block = MockSubsection(
        "block-v1:MITx+course+type@sequential+block@new", "New assignment"
    )

    existing_grade = SimpleNamespace(percent_graded=0.84)
    grade_for_user_not_in_canvas = SimpleNamespace(percent_graded=0.55)

    stub_client = StubCanvasClient(canvas_course_id=2001)

    monkeypatch.setattr(api, "get_canvas_course_id", lambda _course: 2001)
    monkeypatch.setattr(api, "CanvasClient", _stub_canvas_client_factory(stub_client))
    monkeypatch.setattr(
        api,
        "get_subsection_block_user_grades",
        lambda _course: {
            existing_block: {
                HashableUser("learner@example.com"): existing_grade,
                HashableUser("missing@example.com"): grade_for_user_not_in_canvas,
            },
            new_block: {
                HashableUser("learner@example.com"): existing_grade,
            },
        },
    )

    assignment_grades_updated, created_assignments = api.push_edx_grades_to_canvas(
        course
    )

    assert len(stub_client.created_assignments) == 1
    assert stub_client.created_assignments[0] == api.create_assignment_payload(
        new_block
    )

    assert stub_client.updated_assignment_grades == [
        (101, {"grade_data[42][posted_grade]": "84.0%"})
    ]

    assert assignment_grades_updated == {
        existing_block: {
            "status": "updated",
            "canvas_assignment_id": 101,
            "payload": {"grade_data[42][posted_grade]": "84.0%"},
        }
    }
    assert created_assignments == {
        new_block: {
            "status": "created",
            "payload": api.create_assignment_payload(new_block),
        }
    }


@pytest.mark.parametrize(
    ("course", "canvas_course_id", "error_message"),
    [
        (None, None, COURSE_KEY_ID_EMPTY),
        (
            SimpleNamespace(id="course-v1:MITx+course+2026"),
            None,
            "No canvas_course_id set for course: course-v1:MITx+course+2026",
        ),
    ],
)
def test_push_edx_grades_to_canvas_raises_for_missing_inputs(
    monkeypatch, course, canvas_course_id, error_message
):
    """Test that push edx grades to canvas raises for missing inputs."""
    monkeypatch.setattr(api, "get_canvas_course_id", lambda _course: canvas_course_id)

    with pytest.raises(Exception, match=re.escape(error_message)):
        api.push_edx_grades_to_canvas(course)
