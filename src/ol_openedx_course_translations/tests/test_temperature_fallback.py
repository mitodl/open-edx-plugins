"""
Tests for per-model temperature negotiation in LLMProvider._call_llm.

Translation wants the lowest temperature a model will accept. Some models
(OpenAI o-series, some gpt-5 configurations) allow only their default of 1 and
reject anything else — litellm raises locally for some of them and lets others
through to the provider, which returns a 400. Both are treated the same way.

Newer Claude models (Opus 5, Sonnet 5, Opus 4.8/4.7) removed the parameter
outright, so they reject every value including the fallback; those need the
request sent with no temperature at all.
"""

from unittest import mock

import pytest
from litellm import BadRequestError
from litellm.utils import UnsupportedParamsError
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.providers.llm_providers import (
    FALLBACK_TEMPERATURE,
    TRANSLATION_TEMPERATURE,
    OpenAIProvider,
)


@pytest.fixture(autouse=True)
def _clear_temperature_cache():
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001
    yield
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001


@pytest.fixture
def provider():
    return OpenAIProvider("test-key", "gpt-test")


def _response(text="ok"):
    return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=text))])


def _local_rejection():
    return UnsupportedParamsError(
        status_code=400,
        message="models don't support temperature=0.0. Only temperature=1 is supported",
    )


def _api_rejection():
    return BadRequestError(
        message="Unsupported value: 'temperature' does not support 0.0 with this model",
        model="gpt-test",
        llm_provider="openai",
    )


def test_uses_lowest_temperature_when_model_accepts_it(provider):
    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        assert provider._call_llm("system", "user") == "ok"  # noqa: SLF001

    assert completion.call_count == 1
    assert completion.call_args.kwargs["temperature"] == TRANSLATION_TEMPERATURE


@pytest.mark.parametrize("rejection", [_local_rejection, _api_rejection])
def test_retries_at_fallback_when_model_rejects_low_temperature(provider, rejection):
    with mock.patch.object(
        llm_providers, "completion", side_effect=[rejection(), _response()]
    ) as completion:
        assert provider._call_llm("system", "user") == "ok"  # noqa: SLF001

    temperatures = [c.kwargs["temperature"] for c in completion.call_args_list]
    assert temperatures == [TRANSLATION_TEMPERATURE, FALLBACK_TEMPERATURE]


def test_rejection_is_remembered_for_later_calls(provider):
    with mock.patch.object(
        llm_providers, "completion", side_effect=[_local_rejection(), _response()]
    ):
        provider._call_llm("system", "user")  # noqa: SLF001

    # A second provider instance for the same model must not repeat the probe.
    other = OpenAIProvider("test-key", "gpt-test")
    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        other._call_llm("system", "user")  # noqa: SLF001

    assert completion.call_count == 1
    assert completion.call_args.kwargs["temperature"] == FALLBACK_TEMPERATURE


def test_unrelated_errors_are_not_retried(provider):
    error = BadRequestError(
        message="context_length_exceeded", model="gpt-test", llm_provider="openai"
    )
    with (
        mock.patch.object(llm_providers, "completion", side_effect=error) as completion,
        pytest.raises(BadRequestError),
    ):
        provider._call_llm("system", "user")  # noqa: SLF001

    assert completion.call_count == 1


def test_fallback_does_not_leak_across_requested_temperatures(provider):
    """
    A provider asking for its own temperature must get to try it.

    The cache is keyed by requested temperature as well as model, so the
    fallback negotiated for the default does not silently replace the value
    another instance explicitly asked for.
    """
    with mock.patch.object(
        llm_providers, "completion", side_effect=[_local_rejection(), _response()]
    ):
        provider._call_llm("system", "user")  # noqa: SLF001

    warm = OpenAIProvider("test-key", "gpt-test", temperature=0.5)
    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        warm._call_llm("system", "user")  # noqa: SLF001

    assert completion.call_args.kwargs["temperature"] == 0.5  # noqa: PLR2004


def test_validation_uses_a_longer_timeout_without_mutating_the_provider(provider):
    """
    The validation timeout applies to that call only.

    It used to be applied by assigning self.litellm_timeout, which left every
    later call on the same provider instance using the validation timeout.
    """
    original_timeout = provider.litellm_timeout

    with mock.patch.object(
        llm_providers, "completion", return_value=_response("fixed")
    ) as completion:
        provider.validate_translation(
            source_language="en",
            target_language="hi",
            source_content="<p>Hello</p>",
            translated_content="<p>नमस्ते</p>",
        )
        assert (
            completion.call_args.kwargs["timeout"] == llm_providers.VALIDATION_TIMEOUT
        )

        provider._call_llm("system", "user")  # noqa: SLF001
        assert completion.call_args.kwargs["timeout"] == original_timeout

    assert provider.litellm_timeout == original_timeout


def _param_removed_rejection():
    """A model that dropped the parameter rejects the fallback value too."""
    return BadRequestError(
        message="temperature: Extra inputs are not permitted",
        model="claude-opus-5",
        llm_provider="anthropic",
    )


def test_omits_temperature_when_model_rejects_every_value(provider):
    """Models that removed the parameter need the request sent without it."""
    with mock.patch.object(
        llm_providers,
        "completion",
        side_effect=[
            _param_removed_rejection(),
            _param_removed_rejection(),
            _response(),
        ],
    ) as completion:
        assert provider._call_llm("system", "user") == "ok"  # noqa: SLF001

    assert completion.call_count == 3  # noqa: PLR2004
    attempts = completion.call_args_list
    assert attempts[0].kwargs["temperature"] == TRANSLATION_TEMPERATURE
    assert attempts[1].kwargs["temperature"] == FALLBACK_TEMPERATURE
    assert "temperature" not in attempts[2].kwargs


def test_omission_is_remembered_for_later_calls(provider):
    """The two rejected probes are paid once per model, not once per request."""
    with mock.patch.object(
        llm_providers,
        "completion",
        side_effect=[
            _param_removed_rejection(),
            _param_removed_rejection(),
            _response(),
        ],
    ):
        provider._call_llm("system", "user")  # noqa: SLF001

    other = OpenAIProvider("test-key", "gpt-test")
    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        other._call_llm("system", "user")  # noqa: SLF001

    assert completion.call_count == 1
    assert "temperature" not in completion.call_args.kwargs


def test_rejection_without_temperature_is_raised(provider):
    """Nothing is left to try once the parameter has already been dropped."""
    with (
        mock.patch.object(
            llm_providers,
            "completion",
            side_effect=[
                _param_removed_rejection(),
                _param_removed_rejection(),
                _param_removed_rejection(),
            ],
        ) as completion,
        pytest.raises(BadRequestError),
    ):
        provider._call_llm("system", "user")  # noqa: SLF001

    assert completion.call_count == 3  # noqa: PLR2004
