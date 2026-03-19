"""Tests for LanguageCode utility class."""

import pytest
from ol_openedx_auto_select_language.utils import LanguageCode


@pytest.mark.parametrize(
    ("input_code", "expected"),
    [
        ("zh_HANS", "zh-Hans"),
        ("zh_HANT", "zh-Hant"),
        ("zh_HANS_CN", "zh-Hans-CN"),
        ("en_US", "en-US"),
        ("es_419", "es-419"),
        ("pt_br", "pt-BR"),
        ("en", "en"),
        ("fr", "fr"),
        ("de_DE", "de-DE"),
        ("zh-Hans", "zh-Hans"),
        ("zh-Hant", "zh-Hant"),
        ("", ""),
        (None, None),
    ],
)
def test_to_bcp47(input_code, expected):
    """Test conversion from Django/Open edX style to BCP47."""
    assert LanguageCode(input_code).to_bcp47() == expected


@pytest.mark.parametrize(
    ("input_code", "expected"),
    [
        ("zh-Hans", "zh_HANS"),
        ("zh-Hant", "zh_HANT"),
        ("zh-Hans-CN", "zh_HANS_CN"),
        ("en-US", "en_US"),
        ("es-419", "es_419"),
        ("pt-BR", "pt_BR"),
        ("en", "en"),
        ("fr", "fr"),
        ("de-DE", "de_DE"),
        ("zh_HANS", "zh_HANS"),
        ("", ""),
        (None, None),
    ],
)
def test_to_django(input_code, expected):
    """Test conversion from BCP47 to Django/Open edX style."""
    assert LanguageCode(input_code).to_django() == expected
