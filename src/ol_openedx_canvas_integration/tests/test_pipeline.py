"""Tests for the Canvas instructor-dashboard tab pipeline step."""

from unittest.mock import MagicMock, patch

from ol_openedx_canvas_integration.pipeline import (
    CANVAS_TAB_ID,
    AddCanvasInstructorTab,
)
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")


def _step():
    return AddCanvasInstructorTab(filter_type=FILTER_TYPE, running_pipeline=[])


@patch("ol_openedx_canvas_integration.pipeline.get_canvas_course_id")
@patch("ol_openedx_canvas_integration.pipeline.modulestore")
def test_tab_added_when_course_linked_to_canvas(mock_modulestore, mock_get_canvas_id):
    """A Canvas tab is appended when the course has a canvas_id."""
    mock_modulestore.return_value.get_course.return_value = MagicMock()
    mock_get_canvas_id.return_value = "12345"

    result = _step().run_filter(tabs=[], course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["tab_id"] == CANVAS_TAB_ID
    assert tab["title"] == "Canvas"
    assert tab["url"] == f"/instructor-dashboard/{COURSE_KEY}/{CANVAS_TAB_ID}"
    assert "sort_order" in tab


@patch("ol_openedx_canvas_integration.pipeline.get_canvas_course_id")
@patch("ol_openedx_canvas_integration.pipeline.modulestore")
def test_tab_not_added_when_course_not_linked(mock_modulestore, mock_get_canvas_id):
    """No Canvas tab is added when the course has no canvas_id."""
    mock_modulestore.return_value.get_course.return_value = MagicMock()
    mock_get_canvas_id.return_value = None

    result = _step().run_filter(tabs=[], course_key=COURSE_KEY)

    assert result["tabs"] == []


@patch("ol_openedx_canvas_integration.pipeline.get_canvas_course_id")
@patch("ol_openedx_canvas_integration.pipeline.modulestore")
def test_existing_tabs_preserved(mock_modulestore, mock_get_canvas_id):
    """Existing platform tabs are preserved and the Canvas tab is appended."""
    mock_modulestore.return_value.get_course.return_value = MagicMock()
    mock_get_canvas_id.return_value = "12345"

    existing = [{"tab_id": "course_info"}, {"tab_id": "enrollments"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    tab_ids = [tab["tab_id"] for tab in result["tabs"]]
    assert tab_ids == ["course_info", "enrollments", CANVAS_TAB_ID]


@patch("ol_openedx_canvas_integration.pipeline.get_canvas_course_id")
@patch("ol_openedx_canvas_integration.pipeline.modulestore")
def test_tab_not_duplicated(mock_modulestore, mock_get_canvas_id):
    """The Canvas tab is not added twice if it is already present."""
    mock_modulestore.return_value.get_course.return_value = MagicMock()
    mock_get_canvas_id.return_value = "12345"

    existing = [{"tab_id": CANVAS_TAB_ID, "title": "Canvas"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    canvas_tabs = [t for t in result["tabs"] if t["tab_id"] == CANVAS_TAB_ID]
    assert len(canvas_tabs) == 1


@patch("ol_openedx_canvas_integration.pipeline.get_canvas_course_id")
@patch("ol_openedx_canvas_integration.pipeline.modulestore")
def test_lookup_error_is_swallowed(mock_modulestore, mock_get_canvas_id):
    """A failure looking up the course must not break tab generation."""
    mock_modulestore.return_value.get_course.side_effect = Exception("boom")

    existing = [{"tab_id": "course_info"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    # Original tabs are returned unchanged; no exception propagates.
    assert result["tabs"] == existing
    mock_get_canvas_id.assert_not_called()
