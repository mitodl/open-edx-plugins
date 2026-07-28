from __future__ import annotations

from types import SimpleNamespace

import pytest

from ol_openedx_canvas_integration import utils

CANVAS_COURSE_ID_1 = 12345
CANVAS_COURSE_ID_2 = 9999


@pytest.mark.parametrize(
    ("course", "expected"),
    [
        pytest.param(None, None, id="course_is_none"),
        pytest.param(
            SimpleNamespace(other_course_settings={}),
            None,
            id="canvas_id_not_set",
        ),
        pytest.param(
            SimpleNamespace(other_course_settings={"canvas_id": CANVAS_COURSE_ID_1}),
            CANVAS_COURSE_ID_1,
            id="canvas_id_set",
        ),
        pytest.param(
            SimpleNamespace(
                other_course_settings={
                    "canvas_id": CANVAS_COURSE_ID_2,
                    "other_setting": "value",
                    "another_setting": 123,
                }
            ),
            CANVAS_COURSE_ID_2,
            id="canvas_id_with_other_settings",
        ),
    ],
)
def test_get_canvas_course_id(course, expected):
    """Test that get_canvas_course_id returns canvas_id from course settings, or None.

    None is returned when the course is None or canvas_id is absent from settings.
    """
    assert utils.get_canvas_course_id(course=course) == expected


@pytest.mark.parametrize(
    ("task_output", "expected"),
    [
        pytest.param(
            {},
            "0 grades and 0 assignments updated or created",
            id="no_results_key",
        ),
        pytest.param(
            {"results": {}},
            "0 grades and 0 assignments updated or created",
            id="empty_results",
        ),
        pytest.param(
            {"results": {"assignments": 5}},
            "0 grades and 5 assignments updated or created",
            id="only_assignments",
        ),
        pytest.param(
            {"results": {"grades": 10}},
            "10 grades and 0 assignments updated or created",
            id="only_grades",
        ),
        pytest.param(
            {"results": {"grades": 15, "assignments": 3}},
            "15 grades and 3 assignments updated or created",
            id="grades_and_assignments",
        ),
        pytest.param(
            {
                "results": {
                    "grades": 25,
                    "assignments": 7,
                    "other_field": "ignored",
                    "another_field": 99,
                }
            },
            "25 grades and 7 assignments updated or created",
            id="additional_fields_ignored",
        ),
        pytest.param(
            {"results": {"grades": 0, "assignments": 0}},
            "0 grades and 0 assignments updated or created",
            id="zero_counts",
        ),
        pytest.param(
            {"results": {"grades": 1000, "assignments": 500}},
            "1000 grades and 500 assignments updated or created",
            id="high_counts",
        ),
    ],
)
def test_get_task_output_formatted_message(task_output, expected):
    """Test that formatted message correctly reports grade and assignment counts."""
    assert utils.get_task_output_formatted_message(task_output) == expected
