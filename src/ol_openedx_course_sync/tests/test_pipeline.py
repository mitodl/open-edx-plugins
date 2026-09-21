"""Tests for the course sync instructor-dashboard tab pipeline step."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from ol_openedx_course_sync.constants import COURSE_SYNC_ACTIONS_TAB_ID
from ol_openedx_course_sync.pipeline import AddCourseSyncActionsInstructorTab
from opaque_keys.edx.keys import CourseKey

FILTER_TYPE = "org.openedx.learning.instructor.dashboard.tabs.requested.v1"
COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")
INSTRUCTOR_MFE_URL = "http://localhost/apps/instructor-dashboard"

STAFF_USER = SimpleNamespace(is_staff=True)
NON_STAFF_USER = SimpleNamespace(is_staff=False)
ACTIVE_MAPPINGS = ["a-mapping"]


def _step():
    return AddCourseSyncActionsInstructorTab(
        filter_type=FILTER_TYPE, running_pipeline=[]
    )


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_added_for_staff_on_sync_source(mock_get_mappings):
    """The tab is appended for a staff user on an active sync source course."""
    mock_get_mappings.return_value = ACTIVE_MAPPINGS

    result = _step().run_filter(tabs=[], user=STAFF_USER, course_key=COURSE_KEY)

    tabs = result["tabs"]
    assert len(tabs) == 1
    tab = tabs[0]
    assert tab["tab_id"] == COURSE_SYNC_ACTIONS_TAB_ID
    assert tab["title"] == "Course Sync Actions"
    # URL path is derived from INSTRUCTOR_MICROFRONTEND_URL's path component.
    assert (
        tab["url"]
        == f"/apps/instructor-dashboard/{COURSE_KEY}/{COURSE_SYNC_ACTIONS_TAB_ID}"
    )
    assert "sort_order" in tab


@pytest.mark.parametrize(
    ("user", "mappings"),
    [
        pytest.param(NON_STAFF_USER, ACTIVE_MAPPINGS, id="non_staff_user"),
        pytest.param(None, ACTIVE_MAPPINGS, id="anonymous_user"),
        pytest.param(STAFF_USER, None, id="course_is_not_a_sync_source"),
        pytest.param(
            STAFF_USER,
            ImproperlyConfigured(
                "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set."
            ),
            id="plugin_not_configured",
        ),
    ],
)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_not_added(mock_get_mappings, user, mappings):
    """
    The tab needs a staff user and an active sync source; anything else omits it.

    A sync target course reaches this as mappings=None, since it is never a
    source. The unconfigured case is the one that has to stay non-raising: this
    runs while building every instructor dashboard.
    """
    if isinstance(mappings, Exception):
        mock_get_mappings.side_effect = mappings
    else:
        mock_get_mappings.return_value = mappings

    result = _step().run_filter(tabs=[], user=user, course_key=COURSE_KEY)

    assert result["tabs"] == []


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_existing_tabs_preserved(mock_get_mappings):
    """Existing platform tabs are preserved and our tab is appended last."""
    mock_get_mappings.return_value = ACTIVE_MAPPINGS

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
        COURSE_SYNC_ACTIONS_TAB_ID,
    ]
    assert tabs[-1]["sort_order"] > max_existing_sort_order


@override_settings(INSTRUCTOR_MICROFRONTEND_URL=INSTRUCTOR_MFE_URL)
@patch("ol_openedx_course_sync.pipeline.get_syncable_course_mappings")
def test_tab_not_duplicated(mock_get_mappings):
    """The tab is not added twice if it is already present."""
    mock_get_mappings.return_value = ACTIVE_MAPPINGS

    existing = [{"tab_id": COURSE_SYNC_ACTIONS_TAB_ID, "title": "Course Sync Actions"}]
    result = _step().run_filter(tabs=existing, user=STAFF_USER, course_key=COURSE_KEY)

    course_sync_tabs = [
        tab for tab in result["tabs"] if tab["tab_id"] == COURSE_SYNC_ACTIONS_TAB_ID
    ]
    assert len(course_sync_tabs) == 1
