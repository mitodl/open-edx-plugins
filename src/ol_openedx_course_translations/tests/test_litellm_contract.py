"""
Tests that run the real litellm ``completion`` without a network call.

The other provider tests patch ``completion`` out, so they cannot tell when a
litellm upgrade changes model routing, the local temperature check, or the
response shape. ``mock_response`` makes litellm return a canned reply after it
has routed the model and validated the parameters, which is the part of its
contract these providers depend on.
"""

from unittest import mock

import litellm
import pytest
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.providers.llm_providers import (
    FALLBACK_TEMPERATURE,
    TRANSLATION_TEMPERATURE,
    AnthropicProvider,
    AzureOpenAIProvider,
    GeminiProvider,
    MistralProvider,
    OpenAIProvider,
)

FAKE_KEY = "not-a-real-key"  # pragma: allowlist secret
REPLY = "translated"


@pytest.fixture
def completion():
    """Spy on the real litellm ``completion`` to see what each attempt sent."""
    with mock.patch.object(
        llm_providers, "completion", wraps=litellm.completion
    ) as spy:
        yield spy


@pytest.fixture(autouse=True)
def _no_azure_credential():
    with mock.patch.object(
        llm_providers, "get_azure_token_provider", return_value=lambda: "entra-token"
    ):
        yield


def _azure(model_name):
    return AzureOpenAIProvider(
        "https://example.openai.azure.com/", "2024-10-21", model_name
    )


@pytest.mark.parametrize(
    "provider",
    [
        OpenAIProvider(FAKE_KEY, "gpt-4.1"),
        _azure("gpt-4.1"),
        GeminiProvider(FAKE_KEY, "gemini-3-pro-preview"),
        MistralProvider(FAKE_KEY, "mistral-large-latest"),
        AnthropicProvider(FAKE_KEY, "claude-sonnet-4-5"),
    ],
    ids=lambda provider: provider.model_name,
)
def test_each_provider_prefix_routes_and_returns_content(provider, completion):
    assert provider._call_llm("system", "user", mock_response=REPLY) == REPLY  # noqa: SLF001
    assert completion.call_count == 1


@pytest.mark.parametrize(
    "provider",
    [
        OpenAIProvider(FAKE_KEY, "gpt-5"),
        OpenAIProvider(FAKE_KEY, "o3-mini"),
        _azure("gpt-5"),
    ],
    ids=lambda provider: provider.model_name,
)
def test_local_temperature_rejection_falls_back(provider, completion):
    """
    litellm rejects temperature=0 for these models before any request is sent.

    The fallback in ``_call_llm`` relies on that rejection being an
    ``UnsupportedParamsError`` that names temperature.
    """
    assert provider._call_llm("system", "user", mock_response=REPLY) == REPLY  # noqa: SLF001

    temperatures = [c.kwargs["temperature"] for c in completion.call_args_list]
    assert temperatures == [TRANSLATION_TEMPERATURE, FALLBACK_TEMPERATURE]
