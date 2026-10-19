"""translate_course's per-file tasks retry a throttled call instead of failing."""

import datetime
import json
from unittest import mock

import pytest
import srt
from celery.exceptions import SoftTimeLimitExceeded
from litellm import AuthenticationError, RateLimitError, Timeout
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.providers.base import TRANSIENT_PROVIDER_ERRORS
from ol_openedx_course_translations.providers.llm_providers import OpenAIProvider

from ol_openedx_course_translations import tasks

SOURCES = {"<p>Conduction moves heat.</p>", "<p>Welcome.</p>", "Heat Transfer"}


def _transient(error_class):
    return error_class(message="r", model="gpt-test", llm_provider="openai")


def _cue():
    return srt.Subtitle(
        1, datetime.timedelta(0), datetime.timedelta(seconds=1), "Hello."
    )


def _translate_file(path):
    return tasks.translate_file_task.apply(
        args=(str(path), "en", "hi", "openai", "gpt-test", "openai", "gpt-test")
    )


def _translate_updates(path):
    return tasks.translate_info_updates_task.apply(
        args=(str(path), "en", "hi", "openai", "gpt-test")
    )


def _translate_policy(path):
    return tasks.translate_policy_json_task.apply(
        args=(str(path), "hi", "openai", "gpt-test")
    )


def _html_file(tmp_path):
    path = tmp_path / "intro.html"
    path.write_text("<p>Conduction moves heat.</p>", encoding="utf-8")
    return path


def _updates_file(tmp_path):
    path = tmp_path / "updates.items.json"
    items = [
        {"content": "<p>Welcome.</p>"},
        {"content": "<p>Conduction moves heat.</p>"},
    ]
    path.write_text(json.dumps(items), encoding="utf-8")
    return path


def _policy_file(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        json.dumps({"course/2026": {"display_name": "Heat Transfer"}}),
        encoding="utf-8",
    )
    return path


TASKS = [
    pytest.param(_translate_file, _html_file, id="file"),
    pytest.param(_translate_updates, _updates_file, id="updates"),
    pytest.param(_translate_policy, _policy_file, id="policy"),
]


@pytest.mark.parametrize("error_class", TRANSIENT_PROVIDER_ERRORS)
@pytest.mark.parametrize(("run", "make_file"), TASKS)
def test_a_throttled_call_is_retried_from_the_source(
    tmp_path, run, make_file, error_class
):
    """
    A throttled call must reach autoretry_for.

    Returned as an error, it would fail the whole course. The retry has to
    start again from the English source: in the updates file the first item is
    translated before the second one throttles.
    """
    path = make_file(tmp_path)
    throttled = []
    provider = mock.Mock()

    def translate_text(text, *args, **kwargs):  # noqa: ARG001
        if text != "<p>Welcome.</p>" and not throttled:
            throttled.append(text)
            raise _transient(error_class)
        return "ऊष्मा"

    provider.translate_text.side_effect = translate_text

    with mock.patch.object(tasks, "get_translation_provider", return_value=provider):
        result = run(path)

    assert result.get()["status"] == "success"
    assert throttled
    sent = {call.args[0] for call in provider.translate_text.call_args_list}
    assert sent <= SOURCES
    assert "ऊष्मा" in path.read_text(encoding="utf-8")


@pytest.mark.parametrize(("run", "make_file"), TASKS)
def test_a_throttle_that_outlasts_the_retries_fails_the_task(tmp_path, run, make_file):
    path = make_file(tmp_path)
    provider = mock.Mock()
    provider.translate_text.side_effect = _transient(RateLimitError)

    with (
        mock.patch.object(tasks, "get_translation_provider", return_value=provider),
        # The eager retry re-raises it as openai's base OpenAIError, so match
        # the message rather than the type.
        pytest.raises(Exception, match="RateLimitError"),
    ):
        run(path).get()

    assert (
        provider.translate_text.call_count
        == tasks.TRANSLATE_FILE_TASK_LIMITS["max_retries"] + 1
    )


@pytest.mark.parametrize(
    "error",
    [
        *(
            pytest.param(_transient(c), id=c.__name__)
            for c in TRANSIENT_PROVIDER_ERRORS
        ),
        pytest.param(SoftTimeLimitExceeded(), id="time-limit"),
    ],
)
def test_a_throttled_subtitle_is_not_reported_as_failed_validation(error):
    """The subtitle wrapper's catch-all used to relabel these "validation failed"."""
    provider = OpenAIProvider("key", "gpt-test")

    with (
        mock.patch.object(provider, "translate_subtitles", side_effect=error),
        pytest.raises(type(error)),
    ):
        provider.translate_srt_with_validation([_cue()], "hi")


@pytest.mark.parametrize(
    ("error", "shrinks"),
    [
        pytest.param(_transient(RateLimitError), False, id="rate-limit"),
        pytest.param(SoftTimeLimitExceeded(), False, id="time-limit"),
        pytest.param(_transient(Timeout), True, id="timeout"),
    ],
)
def test_only_a_timeout_retries_a_subtitle_batch_smaller(error, shrinks):
    """All three match the keywords, but only a timeout can be a size problem."""
    provider = OpenAIProvider("key", "gpt-test")

    with (
        mock.patch.object(llm_providers, "completion", side_effect=error) as completion,
        pytest.raises(type(error)),
    ):
        provider.translate_subtitles([_cue(), _cue()], "hi")

    assert (completion.call_count > 1) is shrinks


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("bad markup"), id="bug"),
        pytest.param(
            AuthenticationError(message="bad key", model="m", llm_provider="openai"),
            id="provider-error",
        ),
    ],
)
def test_any_other_failure_is_still_reported_without_a_retry(tmp_path, error):
    path = _html_file(tmp_path)
    provider = mock.Mock()
    provider.translate_text.side_effect = error

    with mock.patch.object(tasks, "get_translation_provider", return_value=provider):
        result = _translate_file(path)

    assert result.get() == {"status": "error", "file": str(path), "error": str(error)}
    assert provider.translate_text.call_count == 1
