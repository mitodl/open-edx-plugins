"""Base classes for translation providers."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import srt

logger = logging.getLogger(__name__)


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
