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

    def test_returns_course_language(self, rf, mock_authenticated_user, mocker):
        """Test returns language of a valid course."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_course = mocker.Mock()
        mock_course.language = "es"
        mock_overview_cls.get_from_id.return_value = mock_course

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"language": "es"}

    def test_converts_language_to_bcp47(self, rf, mock_authenticated_user, mocker):
        """Test Django-style language converted to BCP47."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_course = mocker.Mock()
        mock_course.language = "zh_HANS"
        mock_overview_cls.get_from_id.return_value = mock_course

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"language": "zh-Hans"}

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

    def test_returns_empty_string_when_no_language(
        self, rf, mock_authenticated_user, mocker
    ):
        """Test returns empty string when language is not set."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_course = mocker.Mock()
        mock_course.language = ""
        mock_overview_cls.get_from_id.return_value = mock_course

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"language": ""}

    def test_returns_none_when_language_is_none(
        self, rf, mock_authenticated_user, mocker
    ):
        """Test returns None when course language is None."""
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_course = mocker.Mock()
        mock_course.language = None
        mock_overview_cls.get_from_id.return_value = mock_course

        request = rf.get("/")
        request.user = mock_authenticated_user
        view = CourseLanguageView()
        response = view.get(
            request,
            course_key_string="course-v1:edX+DemoX+2024",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {"language": None}
