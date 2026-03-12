"""Tests for CourseLanguageView API view."""

import pytest
from django.test import RequestFactory
from ol_openedx_auto_select_language.views import CourseLanguageView
from opaque_keys import InvalidKeyError
from rest_framework import status

MODULE = "ol_openedx_auto_select_language.views"


@pytest.fixture
def rf():
    """Provide a Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
def mock_authenticated_user(mocker):
    """Provide a mock authenticated user."""
    user = mocker.Mock()
    user.is_authenticated = True
    return user


class TestCourseLanguageView:
    """Tests for CourseLanguageView."""

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
        self,
        rf,
        mock_authenticated_user,
        mocker,
        course_lang,
        expected_lang,
    ):
        """Test returns language converted to BCP47."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_course = mocker.Mock()
        mock_course.language = course_lang
        mock_overview_cls.get_from_id.return_value = mock_course

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"language": expected_lang}

    def test_returns_400_for_invalid_course_key(
        self, rf, mock_authenticated_user, mocker
    ):
        """Test returns 400 for an invalid course key."""
        mock_course_key = mocker.patch(f"{MODULE}.CourseKey")
        mock_course_key.from_string.side_effect = InvalidKeyError(
            "key_cls", "invalid-key"
        )

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(request, course_key_string="invalid-key")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "Invalid course_key."}

    def test_returns_404_for_nonexistent_course(
        self, rf, mock_authenticated_user, mocker
    ):
        """Test returns 404 when course does not exist."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_overview_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_overview_cls.get_from_id.side_effect = mock_overview_cls.DoesNotExist(
            "Not found"
        )

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data == {"error": "Course not found."}

    def test_returns_400_for_unexpected_error(
        self, rf, mock_authenticated_user, mocker
    ):
        """Test returns 400 for unexpected errors."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        # DoesNotExist must be a valid exception class so the
        # view's `except CourseOverview.DoesNotExist:` doesn't
        # raise TypeError when evaluating the except clause.
        mock_overview_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
        mock_overview_cls.get_from_id.side_effect = RuntimeError("Unexpected")

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data == {"error": "An unexpected error occurred."}
