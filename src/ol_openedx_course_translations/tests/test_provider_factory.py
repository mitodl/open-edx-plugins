"""
Provider wiring: which class a name builds, and what prompt that class sends.

The name-to-class mapping is a table, so nothing but a test says a name
reaches the class that speaks to that vendor — a swapped row would send every
request to the wrong API with a key it will not accept. The subtitle prompt
is shared by inheritance for the same reason: it used to be copied into each
provider, and a correction reached whichever copies someone remembered.
"""

import pytest
from ol_openedx_course_translations.providers.llm_providers import (
    AnthropicProvider,
    GeminiProvider,
    MistralProvider,
    OpenAIProvider,
)
from ol_openedx_course_translations.utils.course_translations import (
    get_translation_provider,
)

FAKE_KEY = "test-key"  # pragma: allowlist secret


@pytest.fixture(autouse=True)
def _configured(settings):
    settings.TRANSLATIONS_PROVIDERS = {
        name: {"api_key": FAKE_KEY, "default_model": f"{name}-test"}
        for name in ("anthropic", "gemini", "mistral", "openai")
    }


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("anthropic", AnthropicProvider),
        ("gemini", GeminiProvider),
        ("mistral", MistralProvider),
        ("openai", OpenAIProvider),
    ],
)
def test_each_provider_name_builds_its_own_class(name, expected):
    assert isinstance(get_translation_provider(name, f"{name}-test"), expected)


def test_a_configured_name_with_no_class_is_rejected(settings):
    """
    Settings can name a provider the code does not implement.

    A name absent from settings raises KeyError on the config lookup first,
    so this branch is what a typo in TRANSLATIONS_PROVIDERS reaches.
    """
    settings.TRANSLATIONS_PROVIDERS = {"nope": {"api_key": FAKE_KEY}}

    with pytest.raises(ValueError, match="Unknown provider"):
        get_translation_provider("nope", "model")


def test_every_provider_sends_the_same_subtitle_prompt_but_mistral():
    """
    Mistral needs one extra rule; the rest share the prompt exactly.

    Pinned because the difference is the only reason the hook exists — if it
    stops being the only difference, the shared prompt is the wrong shape.
    """
    prompts = {
        name: cls(FAKE_KEY, f"{name}-test")._get_subtitle_system_prompt("hi")  # noqa: SLF001
        for name, cls in (
            ("anthropic", AnthropicProvider),
            ("gemini", GeminiProvider),
            ("mistral", MistralProvider),
            ("openai", OpenAIProvider),
        )
    }

    assert prompts["openai"] == prompts["gemini"] == prompts["anthropic"]
    assert prompts["mistral"] == prompts["openai"].replace(
        "8. Maintain 1:1 mapping - every Source gets exactly one Target.\n",
        "8. Maintain 1:1 mapping - every Source gets exactly one Target.\n"
        "9. Even if you merge fragmented sentences in translation, maintain "
        "1:1 ID mapping by adding blank translation for the merged fragment.\n",
    )
