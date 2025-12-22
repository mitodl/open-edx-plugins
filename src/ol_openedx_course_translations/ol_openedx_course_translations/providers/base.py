"""Base classes for translation providers."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import srt

logger = logging.getLogger(__name__)

# Language code mappings for DeepL API
DEEPL_LANGUAGE_CODES = {
    "fr": "FR",
    "de": "DE",
    "es": "ES",
    "pt": "PT-PT",
    "pt-br": "PT-BR",
    "hi": "HI",
    "ar": "AR",
    "zh": "ZH",
    "kr": "KO",
    "ja": "JA",
    "id": "ID",
    "ru": "RU",
    "el": "EL",
    "tr": "TR",
    "sq": "SQ",
}

# Human-readable language names for prompts
LANGUAGE_DISPLAY_NAMES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt-br": "Português - Brasil",  # Fixed EN DASH
    "ru": "Русский",
    "hi": "हिंदी",
    "el": "ελληνικά",
    "ja": "日本語",
    "ar": "العربية",
    "zh": "中文",
    "tr": "Türkçe",
    "sq": "Shqip",
    "kr": "한국어",
    "id": "Bahasa Indonesia",
}


def load_glossary(
    target_language_code: str, glossary_directory: str | None = None
) -> str:
    """
    Load a language glossary from glossaries directory.

    Args:
        target_language_code: Language code for the glossary file
        glossary_directory: Path to directory containing glossary files

    Returns:
        Glossary content as string, empty if not found or directory not provided
    """
    if not glossary_directory:
        return ""

    glossary_file_path = Path(glossary_directory) / f"{target_language_code}.txt"
    if not glossary_file_path.exists():
        logger.warning("Glossary file not found: %s", glossary_file_path)
        return ""

    return glossary_file_path.read_text(encoding="utf-8-sig").strip()


class TranslationProvider(ABC):
    """Abstract base class for translation providers."""

    def __init__(self, primary_api_key: str, repair_api_key: str | None = None):
        self.primary_api_key = primary_api_key
        self.repair_api_key = repair_api_key

    @abstractmethod
    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_file: str | None = None,
    ) -> list[srt.Subtitle]:
        """Translate SRT subtitles."""

    @abstractmethod
    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,
        glossary_file: str | None = None,
    ) -> str:
        """Translate plain text or HTML/XML."""

    @abstractmethod
    def translate_document(
        self,
        input_file_path: Path,
        output_file_path: Path,
        source_language: str,
        target_language: str,
    ) -> None:
        """Translate document file."""
