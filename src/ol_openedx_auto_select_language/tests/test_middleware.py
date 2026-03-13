"""Tests for middleware classes and helper functions."""

import pytest
from django.http import HttpResponse, HttpResponseRedirect
from ol_openedx_auto_select_language.constants import (
    ENGLISH_LANGUAGE_CODE,
)
from ol_openedx_auto_select_language.middleware import (
    CourseLanguageCookieMiddleware,
    CourseLanguageCookieResetMiddleware,
    redirect_current_path,
    set_language,
    should_process_request,
)

MODULE = "ol_openedx_auto_select_language.middleware"


@pytest.mark.parametrize(
    ("enabled", "user_type", "expected"),
    [
        (True, "authenticated", True),
        (False, "authenticated", False),
        (True, "anonymous", False),
        (True, "none", False),
    ],
)
def test_should_process_request(  # noqa: PLR0913
    rf,
    settings,
    mocker,
    enabled,
    user_type,
    expected,
):
    """Test should_process_request for various conditions."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = enabled
    request = rf.get("/courses/")
    if user_type == "authenticated":
        request.user = mocker.Mock(is_authenticated=True)
    elif user_type == "anonymous":
        request.user = mocker.Mock(is_authenticated=False)
    elif user_type == "none" and hasattr(request, "user"):
        del request.user
    assert should_process_request(request) is expected


def test_sets_cookie_and_user_preference(rf, mock_user, mocker):
    """Test both cookie and user preference are set."""
    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mock_set_pref = mocker.patch(f"{MODULE}.set_user_preference")

    request = rf.get("/")
    request.user = mock_user
    response = HttpResponse()

    set_language(request, response, "fr")

    mock_helpers.set_language_cookie.assert_called_once_with(request, response, "fr")
    mock_set_pref.assert_called_once()


@pytest.mark.parametrize(
    ("path", "expected_url"),
    [
        (
            "/courses/test-course/",
            "/courses/test-course/",
        ),
        (
            "/courses/test-course/?page=1&lang=en",
            "/courses/test-course/?page=1&lang=en",
        ),
    ],
)
def test_redirects_to_same_path(rf, path, expected_url):
    """Test redirect preserves path and query string."""
    request = rf.get(path)
    result = redirect_current_path(request)
    assert isinstance(result, HttpResponseRedirect)
    assert result.url == expected_url


@pytest.mark.parametrize(
    ("enabled", "is_authenticated", "middleware_cls", "path"),
    [
        # CourseLanguageCookieMiddleware
        (
            True,
            False,
            CourseLanguageCookieMiddleware,
            "/courses/course-v1:edX+DemoX+2024/",
        ),
        (
            False,
            True,
            CourseLanguageCookieMiddleware,
            "/courses/course-v1:edX+DemoX+2024/",
        ),
        # CourseLanguageCookieResetMiddleware
        (True, False, CourseLanguageCookieResetMiddleware, "/some-cms-page/"),
        (False, True, CourseLanguageCookieResetMiddleware, "/some-cms-page/"),
    ],
)
def test_skips_processing(  # noqa: PLR0913
    rf, settings, mocker, enabled, is_authenticated, middleware_cls, path
):
    """Test response unchanged when processing is skipped."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = enabled
    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")

    middleware = middleware_cls(mocker.Mock())
    request = rf.get(path)
    request.user = mocker.Mock(is_authenticated=is_authenticated)
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()


def test_forces_english_for_authoring_mfe_origin(rf, settings, mock_user, mocker):
    """Test English forced for Course Authoring MFE origin."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get(
        "/courses/course-v1:edX+DemoX+2024/",
        HTTP_ORIGIN="http://authoring.example.com",
    )
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert isinstance(result, HttpResponseRedirect)
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, ENGLISH_LANGUAGE_CODE
    )


@pytest.mark.parametrize(
    "exempt_path",
    ["admin", "sysadmin", "instructor"],
)
def test_forces_english_for_exempt_paths(
    rf,
    settings,
    mock_user,
    mocker,
    exempt_path,
):
    """Test English forced for exempt paths."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = [
        "admin",
        "sysadmin",
        "instructor",
    ]

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get(f"/{exempt_path}/some-page/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert isinstance(result, HttpResponseRedirect)
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, ENGLISH_LANGUAGE_CODE
    )


def test_no_redirect_when_already_english(rf, settings, mock_user, mocker):
    """Test no redirect when cookie is already English."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin"]

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = ENGLISH_LANGUAGE_CODE

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get("/admin/dashboard/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()


@pytest.mark.parametrize(
    ("course_lang", "cookie_lang", "expected_set_lang"),
    [
        ("es", "en", "es"),
        ("zh_HANS", "en", "zh-Hans"),
    ],
)
def test_sets_course_language(  # noqa: PLR0913
    rf,
    settings,
    mock_user,
    mocker,
    course_lang,
    cookie_lang,
    expected_set_lang,
):
    """Test language set and converted to BCP47."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
    mock_overview = mocker.Mock()
    mock_overview.language = course_lang
    mock_overview_cls.get_from_id.return_value = mock_overview
    mock_helpers.get_language_cookie.return_value = cookie_lang

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert isinstance(result, HttpResponseRedirect)
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, expected_set_lang
    )


def test_no_redirect_when_cookie_matches(rf, settings, mock_user, mocker):
    """Test no redirect when cookie matches course language."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
    mock_overview = mocker.Mock()
    mock_overview.language = "fr"
    mock_overview_cls.get_from_id.return_value = mock_overview
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "case": "non_course_path",
            "path": "/dashboard/",
        },
        {
            "case": "course_not_found",
            "path": "/courses/course-v1:edX+DemoX+2024/courseware/",
        },
        {
            "case": "no_language",
            "path": "/courses/course-v1:edX+DemoX+2024/courseware/",
        },
    ],
)
def test_returns_response_unchanged(rf, settings, mock_user, mocker, scenario):
    """Test response unchanged for non-course path, missing course, or no language."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")

    case = scenario["case"]
    if case == "non_course_path":
        pass
    elif case == "course_not_found":
        mock_overview_cls.get_from_id.side_effect = Exception("Not found")
    else:  # no_language
        # spec=[] creates mock without attributes, simulating
        # a course overview with no language attribute set.
        mock_overview_cls.get_from_id.return_value = mocker.Mock(spec=[])

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = rf.get(scenario["path"])
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()
    if case == "non_course_path":
        mock_overview_cls.get_from_id.assert_not_called()


def test_resets_non_english_cookie_to_english(rf, settings, mock_user, mocker):
    """Test non-English cookie reset to English."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
    request = rf.get("/some-cms-page/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, ENGLISH_LANGUAGE_CODE
    )


@pytest.mark.parametrize(
    "cookie_value",
    [ENGLISH_LANGUAGE_CODE, ""],
)
def test_no_change_when_cookie_is_english_or_empty(
    rf, settings, mock_user, mocker, cookie_value
):
    """Test no change when cookie is already English or empty."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = cookie_value

    middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
    request = rf.get("/some-cms-page/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()
