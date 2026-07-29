from __future__ import annotations

from types import SimpleNamespace

from ol_openedx_canvas_integration import context_api


class StubFragment:
    """Minimal Fragment-like stub for plugin context tests."""

    def __init__(self):
        """Initialize storage for injected JavaScript snippets."""
        self.javascript = []

    def add_javascript(self, source):
        """Record added JavaScript content."""
        self.javascript.append(source)


def test_get_resource_bytes_decodes_utf8(monkeypatch):
    """Test that get resource bytes decodes utf8."""
    monkeypatch.setattr(
        context_api.pkg_resources,
        "resource_string",
        lambda _module_name, _path: b"hello-canvas",
    )

    assert (
        context_api.get_resource_bytes("static/js/canvas_integration.js")
        == "hello-canvas"
    )


def test_plugin_context_returns_none_when_no_canvas_course_id(monkeypatch):
    """Test that plugin context returns none when no canvas course id."""
    course = SimpleNamespace(id="course-v1:MITx+Demo+2026")

    monkeypatch.setattr(context_api, "get_canvas_course_id", lambda _course: None)

    context = {"course": course, "sections": []}

    assert context_api.plugin_context(context) is None


def test_plugin_context_adds_canvas_section(monkeypatch):
    """Test that plugin context adds canvas section."""
    course_id = "course-v1:MITx+Demo+2026"
    course = SimpleNamespace(id=course_id)

    monkeypatch.setattr(context_api, "get_canvas_course_id", lambda _course: 9999)
    monkeypatch.setattr(context_api, "Fragment", StubFragment)
    monkeypatch.setattr(
        context_api,
        "get_resource_bytes",
        lambda _path: "console.log('canvas');",
    )
    monkeypatch.setattr(
        context_api,
        "reverse",
        lambda name, kwargs: f"/{name}/{kwargs['course_id']}",
    )

    context = {"course": course, "sections": []}
    result = context_api.plugin_context(context)

    assert result is context
    assert len(result["sections"]) == 1

    section = result["sections"][0]
    assert section["section_key"] == "canvas_integration"
    assert section["section_display_name"] == "Canvas"
    assert section["course"] is course
    assert section["add_canvas_enrollments_url"] == (
        f"/add_canvas_enrollments/{course_id}"
    )
    assert section["list_canvas_enrollments_url"] == (
        f"/list_canvas_enrollments/{course_id}"
    )
    assert section["list_canvas_assignments_url"] == (
        f"/list_canvas_assignments/{course_id}"
    )
    assert section["list_canvas_grades_url"] == f"/list_canvas_grades/{course_id}"
    assert section["list_instructor_tasks_url"] == (
        f"/list_instructor_tasks/{course_id}?include_canvas=true"
    )
    assert section["push_edx_grades_url"] == f"/push_edx_grades/{course_id}"
    assert section["template_path_prefix"] == "/"
    assert section["fragment"].javascript == ["console.log('canvas');"]
