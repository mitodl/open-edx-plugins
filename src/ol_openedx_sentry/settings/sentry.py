from __future__ import annotations

import builtins
import importlib
import re
from functools import partial
from typing import Any, Optional, Union

import sentry_sdk


def _load_exception_class(import_specifier: str) -> Union[Exception, None]:
    """Load an exception class to be used for filtering Sentry events.

    This function takes a string representation of an exception class to be filtered out
    of sending to Sentry and returns an uninitialized instance of the class so that it
    can be used as the argument to an `isinstance` method call.

    :param import_specifier: A string containing the full import path for an exception
        class.  ex.  'ValueError' or 'requests.exceptions.HTTPError'
    :type import_specifier: str

    :returns: An uninitialized reference to the exception type to be used in
              `isinstance` comparisons.

    :rtype: Exception
    """
    namespaced_class = import_specifier.rsplit(".", 1)
    if len(namespaced_class) == 1:
        return builtins.__dict__.get(namespaced_class[0])
    exception_module = importlib.import_module(namespaced_class[0])
    return exception_module.__dict__.get(namespaced_class[1])


def sentry_event_filter(
    event,
    hint,
    ignored_types: Optional[list[str]] = None,
    ignored_messages: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Avoid sending events to Sentry that match the specified types or regexes.

    In order to avoid flooding Sentry with events that are not useful and prevent
    wasting those network resources it is possible to filter those events.  This
    function accepts a list of import paths for exception objects and/or a list of
    regular expressions to match against the exception message.

    :param event: Sentry event
    :type event: Sentry event object

    :param hint: Sentry event hint
        https://docs.sentry.io/platforms/python/configuration/filtering/hints/
    :type hint: Sentry event hint object

    :param ignored_types: List of exception classes that should be ignored by Sentry.
        Written as the full import path for the given exception type.  For builtins this
        is just the string representation of the builtin class (e.g. 'ValueError' or
        'requests.exceptions.HTTPError')
    :type ignored_types: List[str]

    :param ignored_messages: List of regular expressions to be matched against the
        contents of the exception message for filtering specific instances of a given
        exception type.
    :type ignored_messages: List[str]

    :returns: An unedited event object or None in the event that the event should be
              filtered.

    :rtype: Optional[Dict[str, Any]]
    """
    exception_info = hint.get("exc_info")
    exception_class = None
    exception_value = ""
    exception_traceback = ""
    if exception_info:
        exception_class, exception_value, exception_traceback = exception_info
        for ignored_type in ignored_types or []:
            ignored_exception_class = _load_exception_class(ignored_type)
            if isinstance(exception_class, type(ignored_exception_class)):
                return None
        for ignored_message in ignored_messages or []:
            if re.search(ignored_message, exception_value or ""):
                return None
    return event


def _load_env_tokens(app_settings) -> dict[str, Any]:
    return getattr(
        app_settings,
        "ENV_TOKENS",
        {
            "SENTRY_IGNORED_EXCEPTION_CLASSES": [],
            "SENTRY_IGNORED_EXCEPTION_MESSAGES": [],
            "SENTRY_DSN": "",
            "SENTRY_ENVIRONMENT": None,
            "SENTRY_SAMPLE_RATE": 0,
            "SENTRY_RELEASE_SPECIFIER": None,
            "SENTRY_SEND_HTTP_REQUEST_BODIES": "small",
        },
    )


def plugin_settings(app_settings):
    env_tokens = _load_env_tokens(app_settings)
    ignored_exceptions = env_tokens.get("SENTRY_IGNORED_EXCEPTION_CLASSES", [])
    ignored_messages = env_tokens.get("SENTRY_IGNORED_EXCEPTION_MESSAGES", [])
    if sentry_dsn := env_tokens.get("SENTRY_DSN"):
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=env_tokens.get("SENTRY_ENVIRONMENT"),
            # Set traces_sample_rate to 1.0 to capture 100%
            # of transactions for performance monitoring.
            # We recommend adjusting this value in production,
            traces_sample_rate=env_tokens.get("SENTRY_TRACES_SAMPLE_RATE", 0),
            # If you wish to associate users to errors (assuming you are using
            # django.contrib.auth) you may enable sending PII data.
            send_default_pii=True,
            # By default the SDK will try to use the SENTRY_RELEASE
            # environment variable, or infer a git commit
            # SHA as release, however you may want to set
            # something more human-readable.
            release=env_tokens.get("SENTRY_RELEASE_SPECIFIER"),
            request_bodies=env_tokens.get("SENTRY_SEND_HTTP_REQUEST_BODIES", "small"),
            before_send=partial(
                sentry_event_filter,
                ignored_types=ignored_exceptions,
                ignored_messages=ignored_messages,
            ),
        )
        app_settings.SENTRY_ENABLED = True
