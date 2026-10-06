"""Attach a non-identifying user id to Sentry events.

With ``send_default_pii`` off the SDK attaches no user at all, so Sentry cannot
count the users an issue affects.  This restores that count without the
identity: ``user.id`` becomes an HMAC of the user's primary key, and nothing
else about the user is sent.

The HMAC key is the whole privacy property.  User primary keys are small
sequential integers, so an unkeyed hash of one is reversed by enumeration.

The middleware only records which request is being served.  The user is read
and written onto the event by ``apply_hashed_user``, which the plugin calls
from ``before_send``.  That is the last hook to touch an event: an event
processor would run before the SDK's own Django user processor (registered on
the current scope, which runs after the isolation scope), and with
``send_default_pii`` on that processor would add email and username back.

``apply_hashed_user`` removes whatever user the SDK attached before it looks
for one to hash.  An event sent outside the middleware (an outer middleware, a
streaming response body, a Celery task) or while the user can't be read
therefore carries no user, never the SDK's.
"""

from __future__ import annotations

import hashlib
import hmac
from contextvars import ContextVar
from typing import Any

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed

USER_HASH_HEX_LENGTH = 16

_current_request: ContextVar[Any] = ContextVar(
    "ol_openedx_sentry_current_request", default=None
)


def hash_user_id(key: bytes, user_pk: object) -> str:
    """Return the keyed, truncated digest that stands in for a user id.

    :param key: Per-deployment HMAC key.
    :param user_pk: The user's primary key.

    :returns: The first ``USER_HASH_HEX_LENGTH`` hex characters of
        ``HMAC-SHA256(key, str(user_pk))``.
    """
    digest = hmac.new(key, str(user_pk).encode(), hashlib.sha256).hexdigest()
    return digest[:USER_HASH_HEX_LENGTH]


def apply_hashed_user(event: dict[str, Any], key: bytes) -> dict[str, Any]:
    """Replace the event's user with the hashed id of the requesting user.

    The user is read here, when the event is sent, rather than when the request
    arrives, because DRF authenticates JWT and OAuth2 requests inside the view.

    :param event: Sentry event payload.
    :param key: Per-deployment HMAC key.

    :returns: The event, with ``user`` either ``{"id": <hash>}`` or absent.
    """
    # Drop first.  With send_default_pii on, the SDK has already filled in id,
    # email, username and ip_address, and reading request.user below can raise
    # (it is lazy, and the database may be the thing that failed).
    event.pop("user", None)
    user = getattr(_current_request.get(), "user", None)
    if user is not None and user.is_authenticated:
        event["user"] = {"id": hash_user_id(key, user.pk)}
    return event


class SentryUserHashMiddleware:
    """Expose the request being served to ``apply_hashed_user``."""

    def __init__(self, get_response):
        """Opt out of the middleware chain when no hash key is configured."""
        if not getattr(settings, "OL_OPENEDX_SENTRY_USER_HASH_KEY", None):
            raise MiddlewareNotUsed
        self.get_response = get_response

    def __call__(self, request):
        """Record the request for the duration of the inner handlers."""
        token = _current_request.set(request)
        try:
            return self.get_response(request)
        finally:
            _current_request.reset(token)
