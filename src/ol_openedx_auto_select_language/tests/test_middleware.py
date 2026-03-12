"""Tests for middleware classes and helper functions."""

import pytest
from django.http import HttpResponse, HttpResponseRedirect
from django.test import RequestFactory
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


@pytest.fixture
def rf():
    """Provide a Django RequestFactory."""
    return RequestFactory()


@pytest.fixture
def mock_user(mocker):
    """Provide a mock authenticated user."""
    return mocker.Mock(is_authenticated=True)


@pytest.fixture
def mock_anonymous_user(mocker):
    """Provide a mock anonymous user."""
    return mocker.Mock(is_authenticated=False)


class TestShouldProcessRequest:
    """Tests for should_process_request helper function."""

    def test_returns_true_when_enabled_and_authenticated(self, rf, settings, mock_user):
        """Test True for authenticated user with feature on."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        request = rf.get("/courses/")
        request.user = mock_user
        assert should_process_request(request) is True

    def test_returns_false_when_disabled(self, rf, settings, mock_user):
        """Test False when feature is disabled."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
        request = rf.get("/courses/")
        request.user = mock_user
        assert should_process_request(request) is False

    def test_returns_false_for_anonymous_user(self, rf, settings, mock_anonymous_user):
        """Test False for anonymous users."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        request = rf.get("/courses/")
        request.user = mock_anonymous_user
        assert should_process_request(request) is False

    def test_returns_false_when_no_user(self, rf, settings):
        """Test False when request has no user attribute."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        request = rf.get("/courses/")
        if hasattr(request, "user"):
            del request.user
        assert should_process_request(request) is False


class TestSetLanguage:
    """Tests for set_language helper function."""

    def test_sets_cookie_and_user_preference(self, rf, mock_user, mocker):
        """Test both cookie and user preference are set."""
        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mock_set_pref = mocker.patch(f"{MODULE}.set_user_preference")

        request = rf.get("/")
        request.user = mock_user
        response = HttpResponse()

        set_language(request, response, "fr")

        mock_helpers.set_language_cookie.assert_called_once_with(
            request, response, "fr"
        )
        mock_set_pref.assert_called_once()


class TestRedirectCurrentPath:
    """Tests for redirect_current_path helper function."""

    def test_redirects_to_same_path(self, rf):
        """Test redirect to the same URL."""
        request = rf.get("/courses/test-course/")
        result = redirect_current_path(request)
        assert isinstance(result, HttpResponseRedirect)
        assert result.url == "/courses/test-course/"

    def test_preserves_query_string(self, rf):
        """Test query string parameters are preserved."""
        request = rf.get("/courses/test-course/?page=1&lang=en")
        result = redirect_current_path(request)
        assert isinstance(result, HttpResponseRedirect)
        assert result.url == "/courses/test-course/?page=1&lang=en"


class TestCourseLanguageCookieMiddleware:
    """Tests for CourseLanguageCookieMiddleware (LMS)."""

    def test_skips_unauthenticated_user(
        self, rf, settings, mock_anonymous_user, mocker
    ):
        """Test response unchanged for unauthenticated users."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/")
        request.user = mock_anonymous_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_skips_when_disabled(self, rf, settings, mock_user, mocker):
        """Test response unchanged when feature is disabled."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = False
        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_forces_english_for_authoring_mfe_origin(
        self, rf, settings, mock_user, mocker
    ):
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
        self, rf, settings, mock_user, mocker, exempt_path
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

    def test_no_redirect_when_already_english(self, rf, settings, mock_user, mocker):
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

    def test_sets_course_language(self, rf, settings, mock_user, mocker):
        """Test language set based on course language."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
        settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_overview = mocker.Mock()
        mock_overview.language = "es"
        mock_overview_cls.get_from_id.return_value = mock_overview
        mock_helpers.get_language_cookie.return_value = "en"

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert isinstance(result, HttpResponseRedirect)
        mock_helpers.set_language_cookie.assert_called_once_with(
            request, response, "es"
        )

    def test_no_redirect_when_cookie_matches(self, rf, settings, mock_user, mocker):
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

    def test_returns_response_for_non_course_path(
        self, rf, settings, mock_user, mocker
    ):
        """Test response unchanged for non-course paths."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
        settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

        mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/dashboard/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_overview_cls.get_from_id.assert_not_called()

    def test_returns_response_when_course_not_found(
        self, rf, settings, mock_user, mocker
    ):
        """Test response unchanged when course lookup fails."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
        settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_overview_cls.get_from_id.side_effect = Exception("Not found")

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_returns_response_when_no_language(self, rf, settings, mock_user, mocker):
        """Test response unchanged when course has no language."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
        settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        # spec=[] creates mock without attributes, simulating
        # a course overview with no language attribute set.
        mock_overview = mocker.Mock(spec=[])
        mock_overview_cls.get_from_id.return_value = mock_overview

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_converts_django_language_to_bcp47(self, rf, settings, mock_user, mocker):
        """Test Django-style lang code converted to BCP47."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True
        settings.COURSE_AUTHORING_MICROFRONTEND_URL = "http://authoring.example.com"
        settings.AUTO_LANGUAGE_SELECTION_EXEMPT_PATHS = []

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_overview_cls = mocker.patch(f"{MODULE}.CourseOverview")
        mock_overview = mocker.Mock()
        mock_overview.language = "zh_HANS"
        mock_overview_cls.get_from_id.return_value = mock_overview
        mock_helpers.get_language_cookie.return_value = "en"

        middleware = CourseLanguageCookieMiddleware(mocker.Mock())
        request = rf.get("/courses/course-v1:edX+DemoX+2024/courseware/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert isinstance(result, HttpResponseRedirect)
        mock_helpers.set_language_cookie.assert_called_once_with(
            request, response, "zh-Hans"
        )


class TestCourseLanguageCookieResetMiddleware:
    """Tests for CourseLanguageCookieResetMiddleware (CMS)."""

    def test_resets_non_english_cookie_to_english(
        self, rf, settings, mock_user, mocker
    ):
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

    def test_no_change_when_already_english(self, rf, settings, mock_user, mocker):
        """Test no change when cookie is already English."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_helpers.get_language_cookie.return_value = ENGLISH_LANGUAGE_CODE

        middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
        request = rf.get("/some-cms-page/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_no_change_when_no_cookie(self, rf, settings, mock_user, mocker):
        """Test no change when there is no language cookie."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")
        mock_helpers.get_language_cookie.return_value = ""

        middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
        request = rf.get("/some-cms-page/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_skips_unauthenticated_user(
        self, rf, settings, mock_anonymous_user, mocker
    ):
        """Test response unchanged for unauthenticated users."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = True

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")

        middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
        request = rf.get("/some-cms-page/")
        request.user = mock_anonymous_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()

    def test_skips_when_disabled(self, rf, settings, mock_user, mocker):
        """Test response unchanged when feature is disabled."""
        settings.ENABLE_AUTO_LANGUAGE_SELECTION = False

        mock_helpers = mocker.patch(f"{MODULE}.lang_pref_helpers")
        mocker.patch(f"{MODULE}.set_user_preference")

        middleware = CourseLanguageCookieResetMiddleware(mocker.Mock())
        request = rf.get("/some-cms-page/")
        request.user = mock_user
        response = HttpResponse()

        result = middleware.process_response(request, response)

        assert result is response
        mock_helpers.set_language_cookie.assert_not_called()
