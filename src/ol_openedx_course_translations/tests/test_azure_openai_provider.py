"""
Tests for the Azure OpenAI provider and its settings.

Azure authenticates with an Entra ID token instead of an API key, so it takes a
different path through provider dispatch, the litellm call, and settings.
The other providers must be unaffected by it.
"""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.test import override_settings
from ol_openedx_course_translations.providers import llm_providers
from ol_openedx_course_translations.providers.llm_providers import (
    AZURE_COGNITIVE_SERVICES_SCOPE,
    AzureOpenAIProvider,
    OpenAIProvider,
)
from ol_openedx_course_translations.settings import production
from ol_openedx_course_translations.settings.common import (
    apply_azure_openai_settings,
)
from ol_openedx_course_translations.utils.course_translations import (
    get_translation_provider,
)

ENDPOINT = "https://mitxonline.openai.azure.com/"
API_VERSION = "2024-10-21"

FAKE_KEY = "not-a-real-key"  # pragma: allowlist secret

OTHER_PROVIDERS = {
    "default_provider": "mistral",
    "openai": {"api_key": FAKE_KEY, "default_model": "gpt-5.2"},
    "gemini": {"api_key": FAKE_KEY, "default_model": "gemini-3-pro-preview"},
    "mistral": {"api_key": FAKE_KEY, "default_model": "mistral-large-latest"},
}


@pytest.fixture(autouse=True)
def _reset_process_state():
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001
    llm_providers.get_azure_token_provider.cache_clear()
    yield
    llm_providers._MODEL_TEMPERATURES.clear()  # noqa: SLF001
    llm_providers.get_azure_token_provider.cache_clear()


@pytest.fixture
def token_provider():
    """Stand in for azure-identity so no credential lookup happens."""
    provider = mock.Mock(return_value="entra-token")
    with (
        mock.patch.object(llm_providers, "DefaultAzureCredential") as credential,
        mock.patch.object(
            llm_providers, "get_bearer_token_provider", return_value=provider
        ) as get_provider,
    ):
        yield SimpleNamespace(
            provider=provider, credential=credential, get_provider=get_provider
        )


def _response(text="ok"):
    return mock.Mock(choices=[mock.Mock(message=mock.Mock(content=text))])


def test_azure_model_string_uses_the_deployment_name():
    provider = AzureOpenAIProvider(ENDPOINT, API_VERSION, "gpt-5-mini")

    assert provider.model_name == "azure/gpt-5-mini"


def test_azure_requires_a_deployment_name():
    with pytest.raises(ValueError, match="AzureOpenAIProvider"):
        AzureOpenAIProvider(ENDPOINT, API_VERSION, None)


def test_azure_call_sends_endpoint_and_token_provider_without_api_key(
    token_provider,
):
    provider = AzureOpenAIProvider(ENDPOINT, API_VERSION, "gpt-5.2")

    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        assert provider._call_llm("system", "user") == "ok"  # noqa: SLF001

    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "azure/gpt-5.2"
    assert kwargs["api_base"] == ENDPOINT
    assert kwargs["api_version"] == API_VERSION
    assert kwargs["azure_ad_token_provider"] is token_provider.provider
    assert "api_key" not in kwargs
    token_provider.get_provider.assert_called_once_with(
        token_provider.credential.return_value, AZURE_COGNITIVE_SERVICES_SCOPE
    )


def test_azure_temperature_fallback_keeps_azure_auth(token_provider):
    rejection = llm_providers.BadRequestError(
        message="Unsupported value: 'temperature' does not support 0.0",
        model="gpt-5.2",
        llm_provider="azure",
    )
    provider = AzureOpenAIProvider(ENDPOINT, API_VERSION, "gpt-5.2")

    with mock.patch.object(
        llm_providers, "completion", side_effect=[rejection, _response()]
    ) as completion:
        provider._call_llm("system", "user")  # noqa: SLF001

    retry = completion.call_args_list[1].kwargs
    assert retry["temperature"] == llm_providers.FALLBACK_TEMPERATURE
    assert retry["azure_ad_token_provider"] is token_provider.provider
    assert "api_key" not in retry


def test_credential_is_created_once_per_process(token_provider):
    first = AzureOpenAIProvider(ENDPOINT, API_VERSION, "gpt-5.2")
    second = AzureOpenAIProvider(ENDPOINT, API_VERSION, "gpt-4o")

    with mock.patch.object(llm_providers, "completion", return_value=_response()):
        first._call_llm("system", "user")  # noqa: SLF001
        second._call_llm("system", "user")  # noqa: SLF001
        first._call_llm("system", "user")  # noqa: SLF001

    token_provider.credential.assert_called_once_with()
    token_provider.get_provider.assert_called_once()


def test_openai_call_is_unchanged(token_provider):
    provider = OpenAIProvider(FAKE_KEY, "gpt-5.2")

    with mock.patch.object(
        llm_providers, "completion", return_value=_response()
    ) as completion:
        provider._call_llm("system", "user")  # noqa: SLF001

    kwargs = completion.call_args.kwargs
    assert kwargs["model"] == "openai/gpt-5.2"
    assert kwargs["api_key"] == FAKE_KEY
    assert not {"api_base", "api_version", "azure_ad_token_provider"} & kwargs.keys()
    token_provider.credential.assert_not_called()


@override_settings(
    TRANSLATIONS_PROVIDERS={
        **OTHER_PROVIDERS,
        "azure": {
            "api_base": ENDPOINT,
            "api_version": API_VERSION,
            "default_model": "gpt-5.2",
        },
    }
)
def test_dispatch_builds_azure_provider_without_api_key():
    provider = get_translation_provider("azure", "gpt-4o")

    assert isinstance(provider, AzureOpenAIProvider)
    assert provider.model_name == "azure/gpt-4o"
    assert provider.api_base == ENDPOINT
    assert provider.api_version == API_VERSION


@override_settings(TRANSLATIONS_PROVIDERS=OTHER_PROVIDERS)
def test_dispatch_for_key_based_providers_is_unchanged():
    provider = get_translation_provider("openai", "gpt-5.2")

    assert type(provider) is OpenAIProvider
    assert provider.primary_api_key == FAKE_KEY


def _settings(**overrides):
    return SimpleNamespace(
        TRANSLATIONS_PROVIDERS={
            name: dict(config) if isinstance(config, dict) else config
            for name, config in OTHER_PROVIDERS.items()
        },
        **overrides,
    )


def test_azure_settings_are_folded_into_translations_providers():
    settings = _settings(
        AZURE_OPENAI_ENDPOINT=ENDPOINT,
        AZURE_OPENAI_API_VERSION=API_VERSION,
        AZURE_OPENAI_DEFAULT_DEPLOYMENT="gpt-5.2",
    )

    apply_azure_openai_settings(settings)

    assert settings.TRANSLATIONS_PROVIDERS == {
        **OTHER_PROVIDERS,
        "azure": {
            "api_base": ENDPOINT,
            "api_version": API_VERSION,
            "default_model": "gpt-5.2",
        },
    }


@pytest.mark.parametrize("endpoint", [None, ""])
def test_azure_settings_are_skipped_without_an_endpoint(endpoint):
    settings = _settings()
    if endpoint is not None:
        settings.AZURE_OPENAI_ENDPOINT = endpoint

    apply_azure_openai_settings(settings)

    assert settings.TRANSLATIONS_PROVIDERS == OTHER_PROVIDERS


@pytest.mark.parametrize(
    ("overrides", "missing"),
    [
        ({"AZURE_OPENAI_DEFAULT_DEPLOYMENT": "gpt-5.2"}, "AZURE_OPENAI_API_VERSION"),
        ({"AZURE_OPENAI_API_VERSION": API_VERSION}, "AZURE_OPENAI_DEFAULT_DEPLOYMENT"),
        (
            {"AZURE_OPENAI_API_VERSION": "", "AZURE_OPENAI_DEFAULT_DEPLOYMENT": ""},
            "AZURE_OPENAI_API_VERSION, AZURE_OPENAI_DEFAULT_DEPLOYMENT",
        ),
    ],
)
def test_partial_azure_settings_skip_the_provider_with_a_warning(
    overrides, missing, caplog
):
    settings = _settings(AZURE_OPENAI_ENDPOINT=ENDPOINT, **overrides)

    apply_azure_openai_settings(settings)

    assert settings.TRANSLATIONS_PROVIDERS == OTHER_PROVIDERS
    assert f"AZURE_OPENAI_ENDPOINT is set but {missing} is not" in caplog.text


def test_production_settings_keep_the_deployed_providers():
    """
    The production hook runs after the YAML config is loaded.

    It must only add the azure entry, not reset TRANSLATIONS_PROVIDERS to the
    empty defaults that the common settings start from.
    """
    settings = _settings(
        AZURE_OPENAI_ENDPOINT=ENDPOINT,
        AZURE_OPENAI_API_VERSION=API_VERSION,
        AZURE_OPENAI_DEFAULT_DEPLOYMENT="gpt-5.2",
    )

    production.plugin_settings(settings)

    assert settings.TRANSLATIONS_PROVIDERS["openai"]["api_key"] == FAKE_KEY
    assert settings.TRANSLATIONS_PROVIDERS["azure"]["api_base"] == ENDPOINT
