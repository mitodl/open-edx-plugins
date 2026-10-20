"""Tests for CourseLanguageView API view."""

import pytest
from django.contrib.auth.models import AnonymousUser
from ol_openedx_auto_select_language.views import (
    CourseLanguageAnonRateThrottle,
    CourseLanguageUserRateThrottle,
    CourseLanguageView,
    ReleasedLanguagesView,
)
from opaque_keys import InvalidKeyError
from rest_framework import status
from rest_framework.permissions import AllowAny

MODULE = "ol_openedx_auto_select_language.views"


def test_course_language_view_is_throttled():
    """Test that throttling classes are configured."""
    assert CourseLanguageView.throttle_classes == [
        CourseLanguageAnonRateThrottle,
        CourseLanguageUserRateThrottle,
    ]
    assert CourseLanguageAnonRateThrottle.scope == "course_language_anon"
    assert CourseLanguageUserRateThrottle.scope == "course_language_user"


@pytest.mark.parametrize(
    "user_type",
    [
        ("authenticated", "mock_user"),
        ("anonymous", AnonymousUser()),
    ],
)
def test_course_language_view_is_public(request_factory, mock_user, mocker, user_type):
    """Test view uses public access and both user and anonymous users can access."""
    assert CourseLanguageView.permission_classes == [AllowAny]

    # Mock the CourseOverview
    mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
    mock_course = mocker.Mock()
    mock_course.language = "es"
    mock_overview_cls.get_from_id.return_value = mock_course

    # Get the user for this test run
    user_name, user_fixture = user_type
    user = mock_user if user_name == "authenticated" else user_fixture

    request = request_factory.get("/")
    request.user = user
    view = CourseLanguageView()
    response = view.get(request, course_key_string="course-v1:edX+DemoX+2024")

    assert response.status_code == status.HTTP_200_OK
    assert response.data == {"language": "es"}


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


def test_course_language_echoes_cookie_when_learner_language_wins(
    request_factory, mock_user, mocker, learner_language_disabled
):
    """The Footer compares this with the cookie, so it must not switch."""
    learner_language_disabled.return_value = True
    mocker.patch(f"{MODULE}.CourseOverview").get_from_id.return_value.language = "es"
    mocker.patch(f"{MODULE}.lang_pref_helpers.get_language_cookie", return_value="fr")
    request = request_factory.get("/")
    request.user = mock_user

    response = CourseLanguageView().get(request, course_key_string="course-v1:a+b+c")

    assert response.data == {"language": "fr"}


def test_released_languages(request_factory, mocker):
    """The dropdown gets the DarkLang released languages."""
    language = mocker.Mock(code="fr", name="Français")
    language.name = "Français"
    mocker.patch(f"{MODULE}.released_languages", return_value=[language])

    response = ReleasedLanguagesView().get(request_factory.get("/"))

    assert response.data == {
        "enabled": False,
        "languages": [{"code": "fr", "name": "Français"}],
    }


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ({}, ["en", "fr", "hi"]),
        ({"course_id": "course-v1:MITx+T101+2026"}, ["en", "fr"]),
    ],
    ids=["no_course_all_released", "course_own_and_translated_only"],
)
def test_released_languages_for_course(request_factory, mocker, query, expected):
    """In a course, only its own, translated and current languages are listed."""
    languages = []
    for code in ("en", "fr", "hi"):
        language = mocker.Mock(code=code)
        language.name = code
        languages.append(language)
    mocker.patch(f"{MODULE}.released_languages", return_value=languages)
    mocker.patch(f"{MODULE}.course_language_codes", return_value={"en", "fr"})
    mocker.patch(f"{MODULE}.get_language", return_value="en")

    response = ReleasedLanguagesView().get(request_factory.get("/", query))

    assert [language["code"] for language in response.data["languages"]] == expected
