"""Tests for CourseLanguageView API view."""

import pytest
from ol_openedx_auto_select_language.views import CourseLanguageView
from opaque_keys import InvalidKeyError
from rest_framework import status

MODULE = "ol_openedx_auto_select_language.views"


@pytest.mark.parametrize(
    ("course_lang", "expected_lang"),
    [
        ("es", "es"),
        ("zh_HANS", "zh-Hans"),
        ("", ""),
        (None, None),
    ],
)
def test_returns_course_language(
    request_factory,
    mock_user,
    mocker,
    course_lang,
    expected_lang,
):
    """Test returns language converted to BCP47."""
    mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
    mock_course = mocker.Mock()
    mock_course.language = course_lang
    mock_overview_cls.get_from_id.return_value = mock_course

    request = request_factory.get("/")
    request.user = mock_user
    view = CourseLanguageView()
    response = view.get(
        request,
        course_key_string="course-v1:edX+DemoX+2024",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"language": expected_lang}


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "case": "invalid_course_key",
            "course_key_string": "invalid-key",
            "expected_status": status.HTTP_400_BAD_REQUEST,
            "expected_data": {"error": "Invalid course_key."},
        },
        {
            "case": "nonexistent_course",
            "course_key_string": "course-v1:edX+DemoX+2024",
            "expected_status": status.HTTP_404_NOT_FOUND,
            "expected_data": {"error": "Course not found."},
        },
        {
            "case": "unexpected_error",
            "course_key_string": "course-v1:edX+DemoX+2024",
            "expected_status": status.HTTP_400_BAD_REQUEST,
            "expected_data": {"error": "An unexpected error occurred."},
        },
    ],
)
def test_returns_error_responses(
    request_factory,
    mock_user,
    mocker,
    scenario,
):
    """Test error responses for invalid course key and course lookup failures."""
    case = scenario["case"]
    if case == "invalid_course_key":
        mock_course_key = mocker.patch(f"{MODULE}.CourseKey")
        mock_course_key.from_string.side_effect = InvalidKeyError(
            "key_cls", "invalid-key"
        )
    else:
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        # DoesNotExist must be a valid exception class so the
        # view's `except CourseOverview.DoesNotExist:` doesn't
        # raise TypeError when evaluating the except clause.
        mock_overview_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        if case == "nonexistent_course":
            mock_overview_cls.get_from_id.side_effect = mock_overview_cls.DoesNotExist(
                "Not found"
            )
        else:
            mock_overview_cls.get_from_id.side_effect = RuntimeError("Unexpected")

    request = request_factory.get("/")
    request.user = mock_user
    view = CourseLanguageView()
    response = view.get(request, course_key_string=scenario["course_key_string"])

    assert response.status_code == scenario["expected_status"]
    assert response.data == scenario["expected_data"]
