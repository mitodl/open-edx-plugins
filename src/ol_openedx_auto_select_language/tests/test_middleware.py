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
    request_factory,
    settings,
    mocker,
    enabled,
    user_type,
    expected,
):
    """Test `should_process_request` for various conditions."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = enabled
    request = request_factory.get("/courses/")
    if user_type == "authenticated":
        request.user = mocker.Mock(is_authenticated=True)
    elif user_type == "anonymous":
        request.user = mocker.Mock(is_authenticated=False)
    elif user_type == "none" and hasattr(request, "user"):
        del request.user
    assert should_process_request(request) is expected


def test_sets_cookie_and_user_preference(request_factory, mock_user, mocker):
    """
    Test both cookie and user preference are set by `set_language`.
    """
    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mock_set_pref = mocker.patch(f"{MODULE}.set_user_preference")

    request = request_factory.get("/")
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
def test_redirects_to_same_path(request_factory, path, expected_url):
    """Test redirect preserves path and query string."""
    request = request_factory.get(path)
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
def test_middleware_skips_processing(  # noqa: PLR0913
    request_factory, settings, mocker, enabled, is_authenticated, middleware_cls, path
):
    """Test response unchanged when processing is skipped."""
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = enabled
    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")

    middleware = middleware_cls(mocker.Mock())
    request = request_factory.get(path)
    request.user = mocker.Mock(is_authenticated=is_authenticated)
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()


#################### Tests for CourseLanguageCookieMiddleware ####################


@pytest.mark.parametrize(
    ("path", "http_origin", "exempt_paths", "description"),
    [
        (
            "/courses/course-v1:edX+DemoX+2024/",
            "http://authoring.example.com",
            [],
        ),
        (
            "/admin/some-page/",
            None,
            ["admin", "sysadmin", "instructor"],
        ),
        (
            "/sysadmin/some-page/",
            None,
            ["admin", "sysadmin", "instructor"],
        ),
        (
            "/instructor/some-page/",
            None,
            ["admin", "sysadmin", "instructor"],
        ),
    ],
)
def test_forces_english_for_special_paths(  # noqa: PLR0913
    request_factory,
    settings,
    mock_user,
    mocker,
    path,
    http_origin,
    exempt_paths,
):
    """
    Test `CourseLanguageCookieMiddleware` forces English for
    Course Authoring MFE origin and exempt paths.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = exempt_paths

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request_kwargs = {"HTTP_ORIGIN": http_origin} if http_origin else {}
    request = request_factory.get(path, **request_kwargs)
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert isinstance(result, HttpResponseRedirect)
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, ENGLISH_LANGUAGE_CODE
    )


@pytest.mark.parametrize(
    ("path", "cookie_lang", "course_lang"),
    [
        (
            "/admin/dashboard/",
            ENGLISH_LANGUAGE_CODE,
            None,
        ),
        (
            "/courses/course-v1:edX+DemoX+2024/courseware/",
            "fr",
            "fr",
        ),
    ],
)
def test_no_redirect_when_language_matches(  # noqa: PLR0913
    request_factory,
    settings,
    mock_user,
    mocker,
    path,
    cookie_lang,
    course_lang,
):
    """
    Test that `CourseLanguageCookieMiddleware` does not redirect
    when cookie already matches required language.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
    settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
    settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = ["admin"]

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = cookie_lang

    if course_lang:
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_overview = mocker.Mock()
        mock_overview.language = course_lang
        mock_overview_cls.get_from_id.return_value = mock_overview

    middleware = CourseLanguageCookieMiddleware(mocker.Mock())
    request = request_factory.get(path)
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
    request_factory,
    settings,
    mock_user,
    mocker,
    course_lang,
    cookie_lang,
    expected_set_lang,
):
    """
    Test `CourseLanguageCookieMiddleware` sets language and converts to BCP47.
    """
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
    request = request_factory.get("/courses/course-v1:edX+DemoX+2024/courseware/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert isinstance(result, HttpResponseRedirect)
    mock_helpers.set_language_cookie.assert_called_once_with(
        request, response, expected_set_lang
    )


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
def test_returns_response_unchanged(
    request_factory, settings, mock_user, mocker, scenario
):
    """
    Test `CourseLanguageCookieMiddleware` returns unchanged
    response for non-course path, missing course, or no language.
    """
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
    request = request_factory.get(scenario["path"])
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()
    if case == "non_course_path":
        mock_overview_cls.get_from_id.assert_not_called()


####################  Tests for CourseLanguageCookieResetMiddleware ####################


def test_resets_non_english_cookie_to_english(
    request_factory, settings, mock_user, mocker
):
    """
    Test `CourseLanguageCookieResetMiddleware` resets
    non-English cookie to English.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = "fr"

    middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
    request = request_factory.get("/some-cms-page/")
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
    request_factory, settings, mock_user, mocker, cookie_value
):
    """
    Test that CourseLanguageCookieResetMiddleware makes no
    change when cookie is already English or empty.
    """
    settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

    mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
    mocker.patch(f"{MODULE}.set_user_preference")
    mock_helpers.get_language_cookie.return_value = cookie_value

    middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
    request = request_factory.get("/some-cms-page/")
    request.user = mock_user
    response = HttpResponse()

    result = middleware.process_response(request, response)

    assert result is response
    mock_helpers.set_language_cookie.assert_not_called()
