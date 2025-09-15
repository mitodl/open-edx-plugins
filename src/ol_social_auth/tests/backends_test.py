"""Tests for our backend"""

from unittest.mock import MagicMock, patch
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
    assert backend.get_user_details(response) == expected  # noqa: S101


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
        """Dummy setting func"""  # noqa: D401
        return settings.get(name, default)

    strategy.setting.side_effect = _setting

    assert backend.user_data(access_token) == response  # noqa: S101

    request, _ = mocked_responses.calls[0]

    assert request.headers["Authorization"] == "Bearer user_token"  # noqa: S101
    strategy.setting.assert_any_call("API_ROOT", default=None, backend=backend)


def test_authorization_url(backend):
    """Test authorization_url()"""
    with patch(
        "ol_social_auth.backends.OLOAuth2._get_metadata",
        return_value={"authorization_endpoint": "https://example.com/auth"},
    ):
        assert backend.authorization_url() == "https://example.com/auth"  # noqa: S101


def test_access_token_url(backend):
    """Test access_token_url()"""
    with patch(
        "ol_social_auth.backends.OLOAuth2._get_metadata",
        return_value={"token_endpoint": "https://example.com/token"},
    ):
        assert backend.access_token_url() == "https://example.com/token"  # noqa: S101


def test_get_metadata_without_discovery_url(mocker, backend):
    """Should return metadata dict from settings if DISCOVERY_URL is not set"""
    mocker.patch.object(
        backend,
        "setting",
        side_effect=lambda key: {
            "AUTHORIZATION_URL": "https://example.com/auth",
            "ACCESS_TOKEN_URL": "https://example.com/token",
            "DISCOVERY_URL": None,
        }.get(key),
    )
    mocker.patch.object(
        backend, "api_url", return_value="https://example.com/api/users/me"
    )

    metadata = backend._get_metadata()  # noqa: SLF001
    assert metadata == {  # noqa: S101
        "authorization_endpoint": "https://example.com/auth",
        "token_endpoint": "https://example.com/token",
        "userinfo_endpoint": "https://example.com/api/users/me",
    }


def test_get_metadata_with_discovery_url_and_cache(mocker, backend):
    """Should fetch metadata first time, then return cached value without new request"""
    discovery_data = {"authorization_endpoint": "https://disc/auth"}

    mocker.patch.object(
        backend,
        "setting",
        side_effect=lambda key: {
            "DISCOVERY_URL": "https://example.com/.well-known/openid-configuration"
        }.get(key),
    )

    mock_resp = MagicMock()
    mock_resp.json.return_value = discovery_data
    mock_resp.raise_for_status = MagicMock()
    mock_requests = mocker.patch(
        "ol_social_auth.backends.requests.get", return_value=mock_resp
    )

    metadata1 = backend._get_metadata()  # noqa: SLF001
    assert metadata1 == discovery_data  # noqa: S101
    mock_requests.assert_called_once()

    metadata2 = backend._get_metadata()  # noqa: SLF001
    assert metadata2 == discovery_data  # noqa: S101
    mock_requests.assert_called_once()
