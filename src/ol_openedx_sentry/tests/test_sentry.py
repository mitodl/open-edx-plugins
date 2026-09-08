"""Tests for the ol_openedx_sentry Sentry configuration module."""
# ruff: noqa: SLF001 - this suite intentionally exercises private helpers.

import decimal
import logging
import re
import types

from ol_openedx_sentry.settings import sentry
from sentry_sdk.integrations.logging import LoggingIntegration


class TestLoadExceptionClass:
    """Tests for ``_load_exception_class``."""

    def test_builtin_name_resolves(self):
        assert sentry._load_exception_class("ValueError") is ValueError

    def test_dotted_stdlib_path_resolves(self):
        assert (
            sentry._load_exception_class("decimal.InvalidOperation")
            is decimal.InvalidOperation
        )

    def test_bad_module_path_returns_none(self):
        assert sentry._load_exception_class("nonexistent.module.Thing") is None

    def test_valid_module_missing_attribute_returns_none(self):
        assert sentry._load_exception_class("json.NopeError") is None

    def test_non_exception_target_returns_none(self):
        # decimal.Decimal is a valid class but not a BaseException subclass.
        assert sentry._load_exception_class("decimal.Decimal") is None


class TestCompilePatterns:
    """Tests for ``_compile_patterns``."""

    def test_list_of_strings_compiles_each(self):
        patterns = sentry._compile_patterns(["foo", "bar", "baz"])
        expected = 3
        assert len(patterns) == expected
        assert all(isinstance(p, re.Pattern) for p in patterns)

    def test_nested_sequence_entry_is_flattened(self):
        # The mitxonline infra shape: a single entry that is a tuple of
        # fragments expands into one pattern per fragment.
        patterns = sentry._compile_patterns([("foo", "bar")])
        expected = 2
        assert len(patterns) == expected

    def test_non_string_fragment_is_skipped(self):
        patterns = sentry._compile_patterns(["ok", 123])
        expected = 1
        assert len(patterns) == expected
        assert patterns[0].pattern == "ok"

    def test_invalid_regex_is_skipped(self):
        patterns = sentry._compile_patterns(["(unclosed", "valid"])
        expected = 1
        assert len(patterns) == expected
        assert patterns[0].pattern == "valid"

    def test_empty_input_returns_empty_list(self):
        assert sentry._compile_patterns([]) == []

    def test_none_input_returns_empty_list(self):
        assert sentry._compile_patterns(None) == []

    def test_bare_string_is_treated_as_single_pattern(self):
        # A misconfigured bare string must not be iterated character by
        # character (which would compile one regex per char and drop events).
        patterns = sentry._compile_patterns("Failed to pull git repository")
        assert len(patterns) == 1
        assert patterns[0].pattern == "Failed to pull git repository"


def _exc_hint(exc_type, exc_value):
    """Build a Sentry hint carrying ``exc_info`` for the given exception."""
    return {"exc_info": (exc_type, exc_value, None)}


class TestSentryEventFilter:
    """Tests for ``sentry_event_filter``."""

    def test_ignored_class_is_dropped(self):
        result = sentry.sentry_event_filter(
            {},
            _exc_hint(ValueError, ValueError("boom")),
            ignored_classes=(ValueError,),
        )
        assert result is None

    def test_subclass_of_ignored_class_is_dropped(self):
        # KeyError is a subclass of LookupError; issubclass semantics apply.
        result = sentry.sentry_event_filter(
            {},
            _exc_hint(KeyError, KeyError("missing")),
            ignored_classes=(LookupError,),
        )
        assert result is None

    def test_unrelated_exception_passes_through(self):
        # Regression guard: the old isinstance(x, type(y)) bug made two
        # unrelated exception classes match; assert they do NOT.
        event = {}
        result = sentry.sentry_event_filter(
            event,
            _exc_hint(ValueError, ValueError("boom")),
            ignored_classes=(KeyError,),
        )
        assert result is event

    def test_pattern_matches_exception_value(self):
        result = sentry.sentry_event_filter(
            {},
            _exc_hint(ValueError, ValueError("kaboom happened")),
            ignored_patterns=(re.compile("kaboom"),),
        )
        assert result is None

    def test_nested_pattern_shape_filters_without_raising(self):
        patterns = tuple(sentry._compile_patterns([("foo", "bar")]))
        result = sentry.sentry_event_filter(
            {"message": "foo occurred"},
            {},
            ignored_patterns=patterns,
        )
        assert result is None

    def test_log_only_event_message_matches_pattern(self):
        # No exc_info at all: match against the logentry message.
        result = sentry.sentry_event_filter(
            {"logentry": {"message": "please matchme now"}},
            {},
            ignored_patterns=(re.compile("matchme"),),
        )
        assert result is None

    def test_top_level_message_matches_pattern(self):
        result = sentry.sentry_event_filter(
            {"message": "hello world"},
            {},
            ignored_patterns=(re.compile("hello"),),
        )
        assert result is None

    def test_fail_open_when_body_raises(self, mocker):
        # A pattern whose .search raises forces the body to error; the filter
        # must fail open, returning the event and swallowing the exception.
        bad_pattern = mocker.Mock()
        bad_pattern.search.side_effect = RuntimeError("boom")
        event = {"message": "anything"}
        result = sentry.sentry_event_filter(
            event,
            {},
            ignored_patterns=(bad_pattern,),
        )
        assert result is event

    def test_no_matches_returns_same_event_object(self):
        event = {"message": "hello"}
        result = sentry.sentry_event_filter(
            event,
            {},
            ignored_patterns=(re.compile("nomatch"),),
        )
        assert result is event


def _recording_span(mocker, *, trace_id=0x1, span_id=0x2, valid=True, recording=True):
    """Build a mock OTel span/context pair for tagging tests."""
    ctx = mocker.Mock()
    ctx.is_valid = valid
    ctx.trace_id = trace_id
    ctx.span_id = span_id
    span = mocker.Mock()
    span.get_span_context.return_value = ctx
    span.is_recording.return_value = recording
    return span


def _patch_otel(mocker, span):
    """Patch the module's OTel attributes to simulate an installed OTel."""
    otel_trace = mocker.Mock()
    otel_trace.get_current_span.return_value = span
    mocker.patch.object(sentry, "_OTEL_AVAILABLE", True)  # noqa: FBT003
    mocker.patch.object(sentry, "_otel_trace", otel_trace)
    mocker.patch.object(sentry, "_format_trace_id", return_value="formatted-trace")
    mocker.patch.object(sentry, "_format_span_id", return_value="formatted-span")


class TestTagOtelContext:
    """Tests for ``_tag_otel_context`` and its integration in the filter."""

    def test_recording_valid_span_adds_tags(self, mocker):
        _patch_otel(mocker, _recording_span(mocker))
        event = {}
        result = sentry._tag_otel_context(event)
        assert result["tags"]["trace_id"] == "formatted-trace"
        assert result["tags"]["span_id"] == "formatted-span"

    def test_non_recording_span_adds_no_tags(self, mocker):
        _patch_otel(mocker, _recording_span(mocker, recording=False))
        event = {}
        result = sentry._tag_otel_context(event)
        assert "tags" not in result

    def test_invalid_context_adds_no_tags(self, mocker):
        _patch_otel(mocker, _recording_span(mocker, valid=False))
        event = {}
        result = sentry._tag_otel_context(event)
        assert "tags" not in result

    def test_otel_unavailable_returns_event_unchanged(self, mocker):
        mocker.patch.object(sentry, "_OTEL_AVAILABLE", False)  # noqa: FBT003
        event = {"existing": True}
        result = sentry._tag_otel_context(event)
        assert result is event
        assert "tags" not in result

    def test_filter_applies_otel_tags_on_passthrough(self, mocker):
        _patch_otel(mocker, _recording_span(mocker))
        event = {"message": "no match here"}
        result = sentry.sentry_event_filter(
            event,
            {},
            ignored_patterns=(re.compile("nope"),),
        )
        assert result is event
        assert result["tags"]["trace_id"] == "formatted-trace"
        assert result["tags"]["span_id"] == "formatted-span"


class TestCoerceLogEventLevel:
    """Tests for ``_coerce_log_event_level``."""

    def test_none_returns_none(self):
        assert sentry._coerce_log_event_level(None) is None

    def test_int_passes_through(self):
        expected = 40
        assert sentry._coerce_log_event_level(40) == expected

    def test_level_name_resolves(self):
        assert sentry._coerce_log_event_level("ERROR") == logging.ERROR

    def test_bogus_name_returns_none(self):
        assert sentry._coerce_log_event_level("bogus") is None


# A real MITXONLINE-6PK exception value, with the learner identifiers replaced.
PG_INTEGRITY_ERROR = (
    'null value in column "name" of relation "users_user" violates not-null '
    "constraint\n"
    "DETAIL:  Failing row contains (1863408, , 2026-08-07 18:38:14.503726+00, f, "
    "learner@example.invalid, learner@example.invalid, null, f, t, "
    "12d7dfc5-6f84-46db-9383-2d7079434173, 1863408, learner@example.invalid, f)."
)
EXPECTED_RETRIES = 3
EXPECTED_TIMESTAMP = 1757345533.179

PG_PRIMARY_MESSAGE = (
    'null value in column "name" of relation "users_user" violates not-null constraint'
)


class TestScrubPgDetail:
    """Tests for the Postgres ``DETAIL:`` row-echo scrub."""

    def test_detail_line_is_truncated(self):
        scrubbed = sentry._scrub_pg_detail(PG_INTEGRITY_ERROR)
        assert scrubbed.startswith(PG_PRIMARY_MESSAGE)
        assert "learner@example.invalid" not in scrubbed
        assert "12d7dfc5-6f84-46db-9383-2d7079434173" not in scrubbed
        assert "[scrubbed by ol_openedx_sentry]" in scrubbed

    def test_message_without_detail_is_unchanged(self):
        message = "connection to server failed"
        assert sentry._scrub_pg_detail(message) == message

    def test_hint_and_context_after_detail_are_dropped(self):
        text = "boom\nDETAIL:  row data\nHINT:  try again\nCONTEXT:  SQL statement"
        scrubbed = sentry._scrub_pg_detail(text)
        assert "row data" not in scrubbed
        assert "try again" not in scrubbed
        assert "SQL statement" not in scrubbed

    def test_scrubs_exception_values_logentry_and_message(self):
        event = {
            "exception": {"values": [{"value": PG_INTEGRITY_ERROR}]},
            "logentry": {
                "message": PG_INTEGRITY_ERROR,
                "formatted": PG_INTEGRITY_ERROR,
            },
            "message": PG_INTEGRITY_ERROR,
        }
        sentry._scrub_pg_details(event)
        assert "learner@example.invalid" not in repr(event)

    def test_filter_scrubs_on_the_normal_path(self):
        event = {"exception": {"values": [{"value": PG_INTEGRITY_ERROR}]}}
        result = sentry.sentry_event_filter(event, {})
        assert "learner@example.invalid" not in repr(result)

    def test_filter_scrubs_even_when_it_fails_open(self, mocker):
        # The fail-open handler returns the same event dict, so the scrub must
        # already have been applied before anything else can raise.
        mocker.patch.object(sentry, "_event_messages", side_effect=RuntimeError("boom"))
        event = {"exception": {"values": [{"value": PG_INTEGRITY_ERROR}]}}
        result = sentry.sentry_event_filter(event, {})
        assert result is event
        assert "learner@example.invalid" not in repr(result)

    def test_scrubs_breadcrumb_messages(self):
        """LoggingIntegration records the log message as a breadcrumb."""
        event = {
            "breadcrumbs": {
                "values": [
                    {
                        "type": "log",
                        "category": "django_scim.views",
                        "message": PG_INTEGRITY_ERROR,
                    }
                ]
            }
        }
        sentry._scrub_pg_details(event)
        assert "learner@example.invalid" not in repr(event)

    def test_scrubs_logentry_params(self):
        """logger.error("...: %s", exc) puts the exception in logentry.params."""
        event = {
            "logentry": {
                "message": "Unable to complete SCIM call: %s",
                "formatted": "Unable to complete SCIM call: " + PG_INTEGRITY_ERROR,
                "params": [PG_INTEGRITY_ERROR],
            }
        }
        sentry._scrub_pg_details(event)
        assert "learner@example.invalid" not in repr(event)

    def test_scrubs_captured_frame_locals(self):
        """include_local_variables defaults to True, so frame vars carry it too."""
        event = {
            "exception": {
                "values": [
                    {
                        "value": "boom",
                        "stacktrace": {
                            "frames": [
                                {
                                    "function": "save",
                                    "vars": {"exc": PG_INTEGRITY_ERROR, "retries": 3},
                                }
                            ]
                        },
                    }
                ]
            }
        }
        sentry._scrub_pg_details(event)
        assert "learner@example.invalid" not in repr(event)
        frame = event["exception"]["values"][0]["stacktrace"]["frames"][0]
        assert frame["vars"]["retries"] == EXPECTED_RETRIES

    def test_walk_preserves_non_string_leaves(self):
        """The walk must not coerce timestamps, ints or None into strings."""
        event = {
            "timestamp": EXPECTED_TIMESTAMP,
            "level": "error",
            "extra": {"count": 42, "missing": None, "flag": True},
            "message": PG_INTEGRITY_ERROR,
        }
        sentry._scrub_pg_details(event)
        assert event["timestamp"] == EXPECTED_TIMESTAMP
        assert event["extra"] == {"count": 42, "missing": None, "flag": True}
        assert "learner@example.invalid" not in event["message"]


class TestPluginSettings:
    """Tests for ``plugin_settings`` SDK initialization."""

    def test_no_dsn_does_not_init(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(ENV_TOKENS={})
        sentry.plugin_settings(app_settings)
        init.assert_not_called()

    def test_dsn_inits_once_with_defaults(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={"SENTRY_DSN": "https://example.invalid/1"}
        )
        sentry.plugin_settings(app_settings)
        init.assert_called_once()
        kwargs = init.call_args.kwargs
        assert kwargs["send_default_pii"] is False
        assert kwargs["max_request_body_size"] == "never"
        assert kwargs["before_send"] is not None
        integrations = kwargs["integrations"]
        logging_integrations = [
            i for i in integrations if isinstance(i, LoggingIntegration)
        ]
        expected = 1
        assert len(logging_integrations) == expected

    def test_send_default_pii_opt_in(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={
                "SENTRY_DSN": "https://example.invalid/1",
                "SENTRY_SEND_DEFAULT_PII": True,
            }
        )
        sentry.plugin_settings(app_settings)
        assert init.call_args.kwargs["send_default_pii"] is True

    def test_request_bodies_opt_in(self, mocker):
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={
                "SENTRY_DSN": "https://example.invalid/1",
                "SENTRY_SEND_HTTP_REQUEST_BODIES": "small",
            }
        )
        sentry.plugin_settings(app_settings)
        assert init.call_args.kwargs["max_request_body_size"] == "small"

    def test_bare_string_ignored_classes_is_not_iterated_per_char(self, mocker):
        # A misconfigured bare string must resolve as a single class spec, not
        # one spec per character.
        init = mocker.patch.object(sentry.sentry_sdk, "init")
        load = mocker.spy(sentry, "_load_exception_class")
        app_settings = types.SimpleNamespace(
            ENV_TOKENS={
                "SENTRY_DSN": "https://example.invalid/1",
                "SENTRY_IGNORED_EXCEPTION_CLASSES": "ValueError",
            }
        )
        sentry.plugin_settings(app_settings)
        init.assert_called_once()
        load.assert_called_once_with("ValueError")
