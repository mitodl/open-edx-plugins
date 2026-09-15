"""Tests for the course sync instructor-dashboard tab pipeline step."""

from types import SimpleNamespace
from unittest.mock import patch

from django.test import override_settings
from ol_openedx_course_sync.constants import COURSE_SYNC_TAB_ID
from ol_openedx_course_sync.pipeline import AddCourseSyncInstructorTab
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")
INSTRUCTOR_MFE_URL = "http://localhost/apps/instructor-dashboard"

STAFF_USER = SimpleNamespace(is_staff=True)
NON_STAFF_USER = SimpleNamespace(is_staff=False)


def _step():
    return AddCourseSyncInstructorTab(filter_type=FILTER_TYPE, running_pipeline=[])


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_added_for_staff_on_sync_source(mock_get_mappings):
    """The tab is appended for a staff user on an active sync source course."""
    mock_get_mappings.return_value = ["a-mapping"]

    result = _step().run_filter(tabs=[], user=STAFF_USER, course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["tab_id"] == COURSE_SYNC_TAB_ID
    assert tab["title"] == "Course Sync"
    # URL path is derived from INSTRUCTOR_MICROFRONTEND_URL's path component.
    assert tab["url"] == f"/apps/instructor-dashboard/{COURSE_KEY}/{COURSE_SYNC_TAB_ID}"
    assert "sort_order" in tab


@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_not_added_for_non_staff(mock_get_mappings):
    """A non-staff user does not get the tab, even on a sync source course."""
    mock_get_mappings.return_value = ["a-mapping"]

    result = _step().run_filter(tabs=[], user=NON_STAFF_USER, course_key=COURSE_KEY)

    assert result["tabs"] == []


@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_not_added_when_course_is_not_a_sync_source(mock_get_mappings):
    """Courses with no active mapping (including sync targets) do not get the tab."""
    mock_get_mappings.return_value = None

    result = _step().run_filter(tabs=[], user=STAFF_USER, course_key=COURSE_KEY)

    assert result["tabs"] == []


@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_anonymous_user_does_not_raise(mock_get_mappings):
    """A None user is tolerated (no tab, no AttributeError)."""
    mock_get_mappings.return_value = ["a-mapping"]

    result = _step().run_filter(tabs=[], user=None, course_key=COURSE_KEY)

    assert result["tabs"] == []


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_existing_tabs_preserved(mock_get_mappings):
    """Existing platform tabs are preserved and our tab is appended last."""
    mock_get_mappings.return_value = ["a-mapping"]

    existing = [
        {"tab_id": "course_info", "sort_order": 10},
        {"tab_id": "enrollments", "sort_order": 20},
    ]
    # Captured before run_filter, which appends to (and mutates) the list in place.
    max_existing_sort_order = max(tab["sort_order"] for tab in existing)
    result = _step().run_filter(tabs=existing, user=STAFF_USER, course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert [tab["tab_id"] for tab in tabs] == [
        "course_info",
        "enrollments",
        COURSE_SYNC_TAB_ID,
    ]
    assert tabs[-1]["sort_order"] > max_existing_sort_order


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_not_duplicated(mock_get_mappings):
    """The tab is not added twice if it is already present."""
    mock_get_mappings.return_value = ["a-mapping"]

    existing = [{"tab_id": COURSE_SYNC_TAB_ID, "title": "Course Sync"}]
    result = _step().run_filter(tabs=existing, user=STAFF_USER, course_key=COURSE_KEY)

    course_sync_tabs = [
        tab for tab in result["tabs"] if tab["tab_id"] == COURSE_SYNC_TAB_ID
    ]
    assert len(course_sync_tabs) == 1
