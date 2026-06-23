"""Tests for the Rapid Responses instructor-dashboard tab pipeline step."""

from django.test import override_settings
from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_TAB_ID
from ol_openedx_rapid_response_reports.pipeline import AddRapidResponseInstructorTab
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")
INSTRUCTOR_MFE_URL = "http://localhost/apps/instructor-dashboard"


def _step():
    return AddRapidResponseInstructorTab(filter_type=FILTER_TYPE, running_pipeline=[])


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
def test_tab_added():
    """The Rapid Responses tab is appended unconditionally (gated by install)."""
    result = _step().run_filter(tabs=[], course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["tab_id"] == RAPID_RESPONSE_TAB_ID
    assert tab["title"] == "Rapid Responses"
    # URL path is derived from INSTRUCTOR_MICROFRONTEND_URL's path component.
    assert (
        tab["url"] == f"/apps/instructor-dashboard/{COURSE_KEY}/{RAPID_RESPONSE_TAB_ID}"
    )
    assert "sort_order" in tab


def test_existing_tabs_preserved():
    """Platform-provided tabs are preserved and the Rapid Responses tab appended."""
    existing = [
        {"tab_id": "course_info", "sort_order": 10},
        {"tab_id": "enrollments", "sort_order": 20},
    ]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    tabs = result["tabs"]
    tab_ids = [tab["tab_id"] for tab in tabs]
    assert tab_ids == ["course_info", "enrollments", RAPID_RESPONSE_TAB_ID]
    # The tab's sort_order lands after the existing tabs.
    assert tabs[-1]["sort_order"] > existing[-1]["sort_order"]


def test_tab_not_duplicated():
    """The tab is not added twice if it is already present."""
    existing = [{"tab_id": RAPID_RESPONSE_TAB_ID, "title": "Rapid Responses"}]
    result = _step().run_filter(tabs=existing, course_key=COURSE_KEY)

    matching = [t for t in result["tabs"] if t["tab_id"] == RAPID_RESPONSE_TAB_ID]
    assert len(matching) == 1
