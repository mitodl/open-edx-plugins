"""Tests for the hashed Sentry user id middleware."""

import hashlib
import hmac
import json
import types
from functools import partial

import pytest
import sentry_sdk
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import MiddlewareNotUsed
from django.test import Client, RequestFactory
from django.urls import path
from ol_openedx_sentry.settings import sentry
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.transport import Transport

from ol_openedx_sentry import middleware

HASH_KEY = "test-hash-key"  # pragma: allowlist secret
USER_PK = 4217
LEARNER_EMAIL = "learner@example.invalid"
LEARNER_USERNAME = "learner-username"
HASHING_FILTER = partial(sentry.sentry_event_filter, user_hash_key=HASH_KEY.encode())


class FakeTransport(Transport):
    """Collect outgoing events instead of sending them."""

    def __init__(self):
        super().__init__()
        self.events = []

    def capture_envelope(self, envelope):
        self.events.extend(
            item.payload.json for item in envelope.items if item.type == "event"
        )


@pytest.fixture
def sentry_transport():
    """Initialize the real SDK with PII off, and detach it afterwards."""
    transport = FakeTransport()
    sentry_sdk.init(
        dsn="https://k@o0.ingest.sentry.io/0",
        transport=transport,
        send_default_pii=False,
        default_integrations=False,
        before_send=HASHING_FILTER,
    )
    yield transport
    sentry_sdk.get_global_scope().set_client(None)


def _learner():
    return types.SimpleNamespace(
        pk=USER_PK,
        is_authenticated=True,
        email=LEARNER_EMAIL,
        username=LEARNER_USERNAME,
    )


def _capture_in_view(user):
    """Build a view that authenticates late, as DRF does, then reports an error."""

    def view(request):
        request.user = user
        sentry_sdk.capture_exception(RuntimeError("boom"))

    return view


def _failing_view(request):
    request.user = _learner()
    raise RuntimeError("boom")  # noqa: EM101


urlpatterns = [path("fails/", _failing_view)]


class TestHashUserId:
    """Tests for ``hash_user_id``."""

    def test_is_truncated_hmac_sha256_of_the_pk(self):
        expected = hmac.new(
            HASH_KEY.encode(), str(USER_PK).encode(), hashlib.sha256
        ).hexdigest()[: middleware.USER_HASH_HEX_LENGTH]
        assert middleware.hash_user_id(HASH_KEY.encode(), USER_PK) == expected

    def test_differs_from_the_unkeyed_hash(self):
        unkeyed = hashlib.sha256(str(USER_PK).encode()).hexdigest()
        hashed = middleware.hash_user_id(HASH_KEY.encode(), USER_PK)
        assert not unkeyed.startswith(hashed)

    def test_key_changes_the_hash(self):
        assert middleware.hash_user_id(b"one", USER_PK) != middleware.hash_user_id(
            b"two", USER_PK
        )


class TestSentryUserHashMiddleware:
    """Tests for ``SentryUserHashMiddleware`` against the real SDK."""

    def test_unused_without_a_key(self, settings):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = ""
        with pytest.raises(MiddlewareNotUsed):
            middleware.SentryUserHashMiddleware(lambda _request: None)

    def test_event_carries_only_the_hashed_id(self, settings, sentry_transport):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY
        handler = middleware.SentryUserHashMiddleware(_capture_in_view(_learner()))
        handler(RequestFactory().get("/courses/"))
        sentry_sdk.flush()

        (event,) = sentry_transport.events
        assert event["user"] == {
            "id": middleware.hash_user_id(HASH_KEY.encode(), USER_PK)
        }
        serialized = json.dumps(event)
        assert LEARNER_EMAIL not in serialized
        assert LEARNER_USERNAME not in serialized
        assert str(USER_PK) not in json.dumps(event["user"])

    def test_identity_set_by_the_sdk_is_replaced(self, settings, sentry_transport):
        """With send_default_pii on, the SDK fills the user in before we run."""
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY
        handler = middleware.SentryUserHashMiddleware(_capture_in_view(_learner()))
        with sentry_sdk.isolation_scope() as scope:
            scope.add_event_processor(
                lambda event, _hint: {
                    **event,
                    "user": {"email": LEARNER_EMAIL, "ip_address": "192.0.2.1"},
                }
            )
            handler(RequestFactory().get("/courses/"))
        sentry_sdk.flush()

        (event,) = sentry_transport.events
        assert event["user"] == {
            "id": middleware.hash_user_id(HASH_KEY.encode(), USER_PK)
        }

    def test_anonymous_request_has_no_user(self, settings, sentry_transport):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY
        handler = middleware.SentryUserHashMiddleware(_capture_in_view(AnonymousUser()))
        handler(RequestFactory().get("/courses/"))
        sentry_sdk.flush()

        (event,) = sentry_transport.events
        assert "user" not in event

    def test_request_is_forgotten_after_the_response(self, settings, sentry_transport):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY
        handler = middleware.SentryUserHashMiddleware(lambda _request: None)
        request = RequestFactory().get("/courses/")
        request.user = _learner()
        handler(request)
        sentry_sdk.capture_exception(RuntimeError("after the request"))
        sentry_sdk.flush()

        (event,) = sentry_transport.events
        assert "user" not in event

    def test_request_is_forgotten_when_the_handler_raises(self, settings):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY

        def explode(_request):
            raise RuntimeError

        handler = middleware.SentryUserHashMiddleware(explode)
        with pytest.raises(RuntimeError):
            handler(RequestFactory().get("/courses/"))
        assert middleware._current_request.get() is None  # noqa: SLF001


class TestWithDjangoIntegration:
    """The middleware next to the SDK's own Django integration, PII on."""

    def test_unhandled_view_error_carries_only_the_hashed_id(self, settings):
        settings.OL_OPENEDX_SENTRY_USER_HASH_KEY = HASH_KEY
        settings.ROOT_URLCONF = __name__
        settings.MIDDLEWARE = [sentry.USER_HASH_MIDDLEWARE]
        transport = FakeTransport()
        sentry_sdk.init(
            dsn="https://k@o0.ingest.sentry.io/0",
            transport=transport,
            send_default_pii=True,
            default_integrations=False,
            before_send=HASHING_FILTER,
            integrations=[DjangoIntegration()],
        )
        try:
            with sentry_sdk.isolation_scope():
                response = Client(raise_request_exception=False).get("/fails/")
            sentry_sdk.flush()
        finally:
            sentry_sdk.get_global_scope().set_client(None)

        server_error = 500
        assert response.status_code == server_error
        (event,) = transport.events
        assert event["user"] == {
            "id": middleware.hash_user_id(HASH_KEY.encode(), USER_PK)
        }


class TestPluginSettingsUserHash:
    """Tests for the ``SENTRY_USER_HASH_KEY`` wiring in ``plugin_settings``."""

    def test_key_registers_the_middleware_once(self, mocker):
        mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={
                "SENTRY_DSN": "https://example.invalid/1",
                "SENTRY_USER_HASH_KEY": HASH_KEY,
            },
            MIDDLEWARE=["django.contrib.auth.middleware.AuthenticationMiddleware"],
        )
        sentry.plugin_settings(app_settings)
        sentry.plugin_settings(app_settings)
        assert app_settings.OL_OPENEDX_SENTRY_USER_HASH_KEY == HASH_KEY
        assert app_settings.MIDDLEWARE == [
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            sentry.USER_HASH_MIDDLEWARE,
        ]

    def test_key_reaches_before_send(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={
                "SENTRY_DSN": "https://example.invalid/1",
                "SENTRY_USER_HASH_KEY": HASH_KEY,
            },
            MIDDLEWARE=[],
        )
        sentry.plugin_settings(app_settings)
        before_send = init.call_args.kwargs["before_send"]
        assert before_send.keywords["user_hash_key"] == HASH_KEY.encode()

    def test_no_key_leaves_middleware_alone(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={"SENTRY_DSN": "https://example.invalid/1"},
            MIDDLEWARE=[],
        )
        sentry.plugin_settings(app_settings)
        assert app_settings.MIDDLEWARE == []
        assert init.call_args.kwargs["before_send"].keywords["user_hash_key"] is None
