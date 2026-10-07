"""translate_course's per-file tasks retry a throttled call instead of failing."""

import json
from unittest import mock

import pytest
from litellm import RateLimitError

from ol_openedx_course_translations import tasks


def _throttled():
    return RateLimitError(message="r", model="gpt-test", llm_provider="openai")


def _translate_file(path):
    return tasks.translate_file_task.apply(
        args=(str(path), "en", "hi", "openai", "gpt-test", "openai", "gpt-test")
    )


def _translate_updates(path):
    return tasks.translate_info_updates_task.apply(
        args=(str(path), "en", "hi", "openai", "gpt-test")
    )


@pytest.fixture
def html_file(tmp_path):
    path = tmp_path / "intro.html"
    path.write_text("<p>Conduction moves heat.</p>", encoding="utf-8")
    return path


@pytest.fixture
def updates_file(tmp_path):
    path = tmp_path / "updates.items.json"
    path.write_text(json.dumps([{"content": "<p>Welcome.</p>"}]), encoding="utf-8")
    return path


@pytest.mark.parametrize(
    ("run", "path_fixture"),
    [(_translate_file, "html_file"), (_translate_updates, "updates_file")],
)
def test_a_throttled_call_is_retried_not_reported_as_an_error(
    request, run, path_fixture
):
    """
    Returned as {"status": "error"}, one rate limit failed the whole course.

    The task's own handler caught it before autoretry_for could see it.
    """
    path = request.getfixturevalue(path_fixture)
    provider = mock.Mock()
    provider.translate_text.side_effect = [_throttled(), "<p>ऊष्मा</p>"]

    with mock.patch.object(tasks, "get_translation_provider", return_value=provider):
        result = run(path)

    assert result.get()["status"] == "success"
    assert provider.translate_text.call_count == 2  # noqa: PLR2004
    assert "ऊष्मा" in path.read_text(encoding="utf-8")


def test_a_throttle_that_outlasts_the_retries_fails_the_task(html_file):
    provider = mock.Mock()
    provider.translate_text.side_effect = _throttled()

    with (
        mock.patch.object(tasks, "get_translation_provider", return_value=provider),
        # Celery rebuilds the exception across the eager retry, as its base
        # class, so match the message rather than the type.
        pytest.raises(Exception, match="RateLimitError"),
    ):
        _translate_file(html_file).get()

    assert (
        provider.translate_text.call_count
        == tasks.TRANSLATE_FILE_TASK_LIMITS["max_retries"] + 1
    )


def test_any_other_failure_is_still_reported_without_a_retry(html_file):
    provider = mock.Mock()
    provider.translate_text.side_effect = ValueError("bad markup")

    with mock.patch.object(tasks, "get_translation_provider", return_value=provider):
        result = _translate_file(html_file)

    assert result.get() == {
        "status": "error",
        "file": str(html_file),
        "error": "bad markup",
    }
