"""Tests for our backend"""

from urllib.parse import urljoin

import pytest

from ol_social_auth.backends import OLOAuth2

# pylint: disable=redefined-outer-name


@pytest.fixture
def strategy(mocker):
    """Mock strategy"""
    return mocker.Mock()


@pytest.fixture
def backend(strategy):
    """OLOAuth2 backend fixture"""
    return OLOAuth2(strategy)


@pytest.mark.parametrize(
    "response, expected",  # noqa: PT006
    [
        (
            {"username": "abc123", "email": "user@example.com", "name": "Jane Doe"},
            {"username": "abc123", "email": "user@example.com", "name": "Jane Doe"},
        ),
        ({"username": "abc123"}, {"username": "abc123", "email": "", "name": ""}),
    ],
)
def test_get_user_details(backend, response, expected):
    """Test that get_user_details produces expected results"""
    assert backend.get_user_details(response) == expected


def test_user_data(backend, strategy, mocked_responses):
    """Tests that the backend makes a correct appropriate request"""
    access_token = "user_token"  # noqa: S105
    api_root = "http://xpro.example.com/"
    response = {"username": "abc123", "email": "user@example.com", "name": "Jane Doe"}

    mocked_responses.add(
        mocked_responses.GET, urljoin(api_root, "/api/users/me"), json=response
    )
    settings = {"API_ROOT": api_root}

    def _setting(name, *, backend, default=None):  # pylint: disable=unused-argument  # noqa: ARG001
        """Dummy setting func"""
        return settings.get(name, default)

    strategy.setting.side_effect = _setting

    assert backend.user_data(access_token) == response

    request, _ = mocked_responses.calls[0]

    assert request.headers["Authorization"] == "Bearer user_token"
    strategy.setting.assert_any_call("API_ROOT", default=None, backend=backend)


def test_authorization_url(backend, strategy):
    """Test authorization_url()"""
    strategy.setting.return_value = "abc"
    assert backend.authorization_url() == "abc"
    strategy.setting.assert_called_once_with(
        "AUTHORIZATION_URL", default=None, backend=backend
    )


def test_access_token_url(backend, strategy):
    """Test access_token_url()"""
    strategy.setting.return_value = "abc"
    assert backend.access_token_url() == "abc"
    strategy.setting.assert_called_once_with(
        "ACCESS_TOKEN_URL", default=None, backend=backend
    )
