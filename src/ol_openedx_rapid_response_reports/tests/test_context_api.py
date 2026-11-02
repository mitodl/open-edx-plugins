"""Tests for the legacy instructor dashboard plugin context."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ol_openedx_rapid_response_reports.context_api import plugin_context
from opaque_keys.edx.keys import CourseKey

COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")


@pytest.mark.parametrize("is_enabled", [True, False])
def test_plugin_context(is_enabled):
    """The section is only added for courses with rapid response enabled."""
    context = {
        "course": SimpleNamespace(id=COURSE_KEY),
        "sections": [{"section_key": "course_info"}],
    }
    with (
        patch(
            "ol_openedx_rapid_response_reports.context_api.is_rapid_response_enabled_for_course",
            return_value=is_enabled,
        ) as mock_is_enabled,
        patch(
            "ol_openedx_rapid_response_reports.context_api.get_run_data_for_course"
        ) as mock_get_runs,
    ):
        result = plugin_context(context)

    section_keys = [section["section_key"] for section in result["sections"]]
    if is_enabled:
        assert section_keys == ["course_info", "rapid_response"]
        assert result["sections"][-1]["problem_runs"] == mock_get_runs.return_value
    else:
        assert section_keys == ["course_info"]
        mock_get_runs.assert_not_called()
    mock_is_enabled.assert_called_once_with(COURSE_KEY)
