"""Tests for the legacy instructor dashboard plugin context."""

from types import SimpleNamespace
from unittest.mock import patch

import pytest
from ol_openedx_rapid_response_reports.context_api import plugin_context
from opaque_keys.edx.keys import CourseKey

COURSE_KEY = CourseKey.from_string("course-v1:org+course+run")


@pytest.mark.parametrize("has_runs", [True, False])
def test_plugin_context(has_runs):
    """The Rapid Responses section is only added for courses with runs."""
    context = {
        "course": SimpleNamespace(id=COURSE_KEY),
        "sections": [{"section_key": "course_info"}],
    }
    with patch(
        "ol_openedx_rapid_response_reports.context_api.get_run_data_for_course"
    ) as mock_get_runs:
        mock_get_runs.return_value.exists.return_value = has_runs
        result = plugin_context(context)

    section_keys = [section["section_key"] for section in result["sections"]]
    if has_runs:
        assert section_keys == ["course_info", "rapid_response"]
        assert result["sections"][-1]["problem_runs"] == mock_get_runs.return_value
    else:
        assert section_keys == ["course_info"]
    mock_get_runs.assert_called_once_with(course_key=COURSE_KEY)
