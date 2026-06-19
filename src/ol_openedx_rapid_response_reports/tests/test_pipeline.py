"""Tests for the Rapid Responses instructor-dashboard tab pipeline step."""

from ol_openedx_rapid_response_reports.pipeline import (
    RAPID_RESPONSE_TAB_ID,
    AddRapidResponseInstructorTab,
)
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")


def _step():
    return AddRapidResponseInstructorTab(filter_type=FILTER_TYPE, running_pipeline=[])


def test_tab_added():
    """The Rapid Responses tab is appended unconditionally (gated by install)."""
    result = _step().run_filter(tabs=[], course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["tab_id"] == RAPID_RESPONSE_TAB_ID
    assert tab["title"] == "Rapid Responses"
    assert tab["url"] == f"/apps/instructor-dashboard/{COURSE_KEY}/{RAPID_RESPONSE_TAB_ID}"
    assert "sort_order" in tab


def test_existing_tabs_preserved():
    """Platform-provided tabs are preserved and the Rapid Responses tab appended."""
    existing = [{"tab_id": "course_info"}, {"tab_id": "enrollments"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    tab_ids = [tab["tab_id"] for tab in result["tabs"]]
    assert tab_ids == ["course_info", "enrollments", RAPID_RESPONSE_TAB_ID]


def test_tab_not_duplicated():
    """The tab is not added twice if it is already present."""
    existing = [{"tab_id": RAPID_RESPONSE_TAB_ID, "title": "Rapid Responses"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    matching = [t for t in result["tabs"] if t["tab_id"] == RAPID_RESPONSE_TAB_ID]
    assert len(matching) == 1
