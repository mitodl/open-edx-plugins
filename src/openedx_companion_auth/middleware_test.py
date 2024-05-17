"""Middleware tests"""
import pytest


try:
    from django.utils.http import urlquote
except ImportError:
    from urllib.parse import quote as urlquote


@pytest.mark.parametrize("is_enabled", [True, False])
@pytest.mark.parametrize("is_anonymous", [True, False])
@pytest.mark.parametrize(
    "path, allowed_regexes, denied_regexes, should_redirect",
    [
        ("/allowed", [], [], False),
        ("/allowed", [r"^/allowed"], [], False),
        ("/allowed/nested", [r"^/allowed"], [], False),
        ("/denied", [r"^/allowed"], [], True),
        ("/allowed", [], [r"^/allowed"], True),
        ("/allowed/nested", [], [r"^/allowed"], True),
        ("/denied", [], [r"^/allowed"], False),
        ("/allowed", [r"^/allowed"], [r"^/allowed/nested"], False),
        ("/allowed/nested", [r"^/allowed"], [r"^/allowed/nested"], True),
    ],
)
def test_redirect_middleware(
    settings,
    rf,
    mocker,
    is_enabled,
    is_anonymous,
    path,
    allowed_regexes,
    denied_regexes,
    should_redirect,
):  # pylint: disable=too-many-arguments
    """Test that the middleware redirects correctly"""
    settings.MITXPRO_CORE_REDIRECT_LOGIN_URL = "/mitxpro-oauth2/?auth_entry=login"
    settings.MITXPRO_CORE_REDIRECT_ENABLED = is_enabled
    settings.MITXPRO_CORE_REDIRECT_ALLOW_RE_LIST = allowed_regexes
    settings.MITXPRO_CORE_REDIRECT_DENY_RE_LIST = denied_regexes

    from .middleware import RedirectAnonymousUsersToLoginMiddleware

    should_redirect = should_redirect and is_enabled and is_anonymous

    mock_get_response = mocker.Mock()

    middleware = RedirectAnonymousUsersToLoginMiddleware(mock_get_response)

    request = rf.get(path)
    request.user = mocker.Mock(is_anonymous=is_anonymous)
    response = middleware(request)

    if should_redirect:
        mock_get_response.assert_not_called()
        assert response.status_code == 302
        assert (
            response.url
            == "{}&next={}".format(  # pylint: disable=consider-using-f-string
                settings.MITXPRO_CORE_REDIRECT_LOGIN_URL,
                urlquote(request.build_absolute_uri()),
            )
        )
    else:
        mock_get_response.assert_called_once_with(request)
