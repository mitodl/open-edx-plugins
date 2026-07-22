from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from ol_openedx_canvas_integration.constants import DEFAULT_ASSIGNMENT_POINTS

from ol_openedx_canvas_integration import client


class StubSession:
    """Requests session stub that records outbound Canvas API calls."""

    def __init__(self):
        """Initialize header storage and HTTP call capture lists."""
        self.headers = {}
        self.post_calls = []
        self.put_calls = []
        self.delete_calls = []

    def post(self, **kwargs):
        """Record POST request arguments and return a stub response payload."""
        self.post_calls.append(kwargs)
        return {"ok": True, "kwargs": kwargs}

    def put(self, **kwargs):
        """Record PUT request arguments and return a stub response payload."""
        self.put_calls.append(kwargs)
        return {"ok": True, "kwargs": kwargs}

    def delete(self, **kwargs):
        """Record DELETE request arguments and return a stub response payload."""
        self.delete_calls.append(kwargs)
        return {"ok": True, "kwargs": kwargs}


class StubResponse:
    """HTTP response stub for pagination tests."""

    def __init__(self, payload, link_header):
        """Initialize JSON payload and Link header values."""
        self._payload = payload
        self.headers = {"link": link_header}

    def raise_for_status(self):
        """Mimic successful responses by raising nothing."""

    def json(self):
        """Return the configured response payload."""
        return self._payload


class StubCache:
    """Cache stub that captures get and set operations."""

    def __init__(self, get_value=None):
        """Initialize cache hit value and call capture lists."""
        self.get_value = get_value
        self.get_calls = []
        self.set_calls = []

    def get(self, key):
        """Record cache get lookups and return the configured value."""
        self.get_calls.append(key)
        return self.get_value

    def set(self, key, value):
        """Record cache set operations."""
        self.set_calls.append((key, value))


class MockSubsection:
    """Minimal subsection object used for assignment payload generation tests."""

    def __init__(self, location, display_name, due=None):
        """Initialize subsection location, name, and optional due date."""
        self.location = location
        self.display_name = display_name
        self.fields = {"due": due} if due else {}


def _settings():
    return SimpleNamespace(
        CANVAS_BASE_URL="https://canvas.example.edu",
        CANVAS_ACCESS_TOKEN="test-token",  # noqa: S106
    )


def test_get_canvas_session_sets_authorization_header(monkeypatch):
    """Test that get canvas session sets authorization header."""
    session = StubSession()

    monkeypatch.setattr(client, "settings", _settings())
    monkeypatch.setattr(client.requests, "Session", lambda: session)

    result = client.CanvasClient.get_canvas_session()

    assert result is session
    assert result.headers["Authorization"] == "Bearer test-token"


def test_list_canvas_assignments_collects_items_from_all_pages(monkeypatch):
    """Test that list canvas assignments collects items from all pages."""
    session = StubSession()
    page_1 = StubResponse(
        payload=[{"id": 1}],
        link_header='<https://canvas.example.edu/page-2>; rel="next"',
    )
    page_2 = StubResponse(payload=[{"id": 2}], link_header="")

    responses = {
        "https://canvas.example.edu/api/v1/courses/7/assignments?per_page=100": page_1,
        "https://canvas.example.edu/page-2": page_2,
    }
    get_calls = []

    def _get(url, *args, **kwargs):
        get_calls.append((url, args, kwargs))
        return responses[url]

    session.get = _get

    monkeypatch.setattr(
        client.CanvasClient,
        "get_canvas_session",
        staticmethod(lambda: session),
    )
    monkeypatch.setattr(client, "settings", _settings())

    canvas_client = client.CanvasClient(canvas_course_id=7)
    items = canvas_client.list_canvas_assignments()

    assert items == [{"id": 1}, {"id": 2}]
    assert [call[0] for call in get_calls] == [
        ("https://canvas.example.edu/api/v1/courses/7/assignments?per_page=100"),
        "https://canvas.example.edu/page-2",
    ]


def test_list_canvas_enrollments_returns_lowercase_email_map(monkeypatch):
    """Test that list canvas enrollments returns lowercase email map."""
    monkeypatch.setattr(client, "settings", _settings())
    monkeypatch.setattr(
        client.CanvasClient,
        "get_canvas_session",
        staticmethod(StubSession),
    )

    canvas_client = client.CanvasClient(canvas_course_id=8)
    monkeypatch.setattr(
        canvas_client,
        "_paginate",
        lambda _url: [
            {"user": {"login_id": "Learner@Example.com", "id": 11}},
            {"user": {"login_id": "another@example.com", "id": 12}},
        ],
    )

    assert canvas_client.list_canvas_enrollments() == {
        "learner@example.com": 11,
        "another@example.com": 12,
    }


@pytest.mark.parametrize(
    ("cache_value", "paginate_users", "expected_id", "expected_set_calls"),
    [
        pytest.param(
            200,
            [],
            200,
            [],
            id="returns_cached_id_without_fetching",
        ),
        pytest.param(
            None,
            [
                {"id": 301, "login_id": "LEARNER@example.com"},
                {"id": 302, "login_id": "other@example.com"},
            ],
            301,
            [("canvas-id-learner@example.com", 301)],
            id="fetches_and_caches_on_match",
        ),
        pytest.param(
            None,
            [{"id": 302, "login_id": "other@example.com"}],
            None,
            [],
            id="returns_none_when_not_found",
        ),
    ],
)
def test_get_student_id_by_email(
    monkeypatch, cache_value, paginate_users, expected_id, expected_set_calls
):
    """Test that the student id is returned from cache, matched from Canvas, or None."""
    stub_cache = StubCache(get_value=cache_value)

    monkeypatch.setattr(client, "cache", stub_cache)
    monkeypatch.setattr(client, "settings", _settings())
    monkeypatch.setattr(
        client.CanvasClient,
        "get_canvas_session",
        staticmethod(StubSession),
    )

    canvas_client = client.CanvasClient(canvas_course_id=9)
    paginate_called = []
    monkeypatch.setattr(
        canvas_client,
        "_paginate",
        lambda _url, **_kwargs: paginate_called.append(True) or paginate_users,
    )

    student_id = canvas_client.get_student_id_by_email("learner@example.com")

    assert student_id == expected_id
    assert stub_cache.get_calls == ["canvas-id-learner@example.com"]
    assert stub_cache.set_calls == expected_set_calls
    # Cache hit should skip the Canvas API call entirely
    assert bool(paginate_called) == (cache_value is None)


def test_get_canvas_assignments_filters_by_integration_id_and_logs_warning(
    monkeypatch, caplog
):
    """Test that get canvas assignments filters by integration id and logs warning."""
    monkeypatch.setattr(client, "settings", _settings())
    monkeypatch.setattr(
        client.CanvasClient,
        "get_canvas_session",
        staticmethod(StubSession),
    )

    canvas_client = client.CanvasClient(canvas_course_id=10)
    monkeypatch.setattr(
        canvas_client,
        "list_canvas_assignments",
        lambda: [
            {"id": 1, "integration_id": "block-1", "published": True},
            {"id": 2, "integration_id": None, "published": False},
            {"id": 3, "integration_id": "block-3"},
            {"id": 4, "integration_id": None, "published": True},
        ],
    )

    with caplog.at_level("WARNING"):
        result = canvas_client.get_canvas_assignments()

    assert result == {
        "block-1": {"id": 1, "is_published": True},
        "block-3": {"id": 3, "is_published": False},
    }
    assert "missing an integration_id: 2, 4" in caplog.text


def test_assignment_mutation_methods_call_expected_canvas_endpoints(monkeypatch):
    """Test that assignment mutation methods call expected canvas endpoints."""
    session = StubSession()

    monkeypatch.setattr(client, "settings", _settings())
    monkeypatch.setattr(
        client.CanvasClient,
        "get_canvas_session",
        staticmethod(lambda: session),
    )

    canvas_client = client.CanvasClient(canvas_course_id=11)

    create_payload = {"assignment": {"name": "Quiz 1"}}
    update_payload = {"assignment": {"name": "Quiz 1 (updated)"}}
    grades_payload = {"grade_data[7][posted_grade]": "92.0%"}

    canvas_client.create_canvas_assignment(create_payload)
    canvas_client.update_canvas_assignment(77, update_payload)
    canvas_client.delete_canvas_assignment(77)
    canvas_client.update_assignment_grades(77, grades_payload)

    assert session.post_calls[0]["url"] == (
        "https://canvas.example.edu/api/v1/courses/11/assignments"
    )
    assert session.post_calls[0]["json"] == create_payload

    assert session.put_calls[0]["url"] == (
        "https://canvas.example.edu/api/v1/courses/11/assignments/77"
    )
    assert session.put_calls[0]["json"] == update_payload

    assert session.delete_calls[0]["url"] == (
        "https://canvas.example.edu/api/v1/courses/11/assignments/77"
    )

    assert session.post_calls[1]["url"] == (
        "https://canvas.example.edu/api/v1/courses/11/assignments/77/submissions/update_grades"
    )
    assert session.post_calls[1]["data"] == grades_payload


def test_create_assignment_payload_without_due_date():
    """Test that create assignment payload without due date."""
    subsection = MockSubsection(
        "block-v1:MITx+course+type@sequential+block@sec1", "HW 1"
    )

    payload = client.create_assignment_payload(subsection)

    assert payload == {
        "assignment": {
            "name": "HW 1",
            "integration_id": "block-v1:MITx+course+type@sequential+block@sec1",
            "grading_type": "percent",
            "points_possible": DEFAULT_ASSIGNMENT_POINTS,
            "due_at": None,
            "submission_types": ["none"],
            "published": False,
        }
    }


def test_create_assignment_payload_converts_due_date_to_utc_isoformat():
    """Test that create assignment payload converts due date to utc isoformat."""
    due_date = datetime(2026, 5, 7, 12, 34, tzinfo=UTC)
    subsection = MockSubsection("block-2", "Exam", due=due_date)

    payload = client.create_assignment_payload(subsection)

    assert payload["assignment"]["due_at"] == "2026-05-07T12:34:00+00:00"


@pytest.mark.parametrize(
    ("user_id", "grade_percent", "expected"),
    [
        (17, 0.92, ("grade_data[17][posted_grade]", "92.0%")),
        (55, 1.0, ("grade_data[55][posted_grade]", "100.0%")),
    ],
)
def test_update_grade_payload_kv(user_id, grade_percent, expected):
    """Test that update grade payload kv."""
    assert client.update_grade_payload_kv(user_id, grade_percent) == expected
