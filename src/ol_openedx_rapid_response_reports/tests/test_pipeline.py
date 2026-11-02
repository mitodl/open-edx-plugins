"""Tests for the Rapid Responses instructor-dashboard tab pipeline step."""

from unittest.mock import patch

import pytest
from django.test import override_settings
from ol_openedx_rapid_response_reports.constants import RAPID_RESPONSE_TAB_ID
from ol_openedx_rapid_response_reports.pipeline import AddRapidResponseInstructorTab
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")
INSTRUCTOR_MFE_URL = "http://localhost/apps/instructor-dashboard"


def _step():
    return AddRapidResponseInstructorTab(filter_type=FILTER_TYPE, running_pipeline=[])


@pytest.fixture
def mock_runs():
    """Patch the course's rapid response runs; by default the course has runs."""
    with patch(
        "ol_openedx_rapid_response_reports.pipeline.get_run_data_for_course"
    ) as mock_get_runs:
        mock_get_runs.return_value.exists.return_value = True
        yield mock_get_runs


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
def test_tab_added(mock_runs):
    """The Rapid Responses tab is appended for a course with rapid response runs."""
    result = _step().run_filter(tabs=[], user=None, course_key=COURSE_KEY)

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
    mock_runs.assert_called_once_with(COURSE_KEY)


def test_tab_not_added_without_runs(mock_runs):
    """The tab is hidden for courses that have no rapid response runs."""
    mock_runs.return_value.exists.return_value = False
    existing = [{"tab_id": "course_info", "sort_order": 10}]
    result = _step().run_filter(tabs=existing, user=None, course_key=COURSE_KEY)

    assert [tab["tab_id"] for tab in result["tabs"]] == ["course_info"]


@pytest.mark.usefixtures("mock_runs")
def test_existing_tabs_preserved():
    """Platform-provided tabs are preserved and the Rapid Responses tab appended."""
    existing = [
        {"tab_id": "course_info", "sort_order": 10},
        {"tab_id": "enrollments", "sort_order": 20},
    ]
    # Captured before run_filter, which appends to (and mutates) the list in place.
    max_existing_sort_order = max(tab["sort_order"] for tab in existing)
    result = _step().run_filter(tabs=existing, user=None, course_key=COURSE_KEY)

    tabs = result["tabs"]
    tab_ids = [tab["tab_id"] for tab in tabs]
    assert tab_ids == ["course_info", "enrollments", RAPID_RESPONSE_TAB_ID]
    # The tab's sort_order lands after the existing tabs.
    assert tabs[-1]["sort_order"] > max_existing_sort_order


@pytest.mark.usefixtures("mock_runs")
def test_tab_not_duplicated():
    """The tab is not added twice if it is already present."""
    existing = [{"tab_id": RAPID_RESPONSE_TAB_ID, "title": "Rapid Responses"}]
    result = _step().run_filter(tabs=existing, user=None, course_key=COURSE_KEY)

    matching = [t for t in result["tabs"] if t["tab_id"] == RAPID_RESPONSE_TAB_ID]
    assert len(matching) == 1
