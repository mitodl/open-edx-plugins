"""Base classes for translation providers."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path

import srt

logger = logging.getLogger(__name__)

MAX_SUBTITLE_TRANSLATION_RETRIES = 1


def load_glossary(target_language: str, glossary_directory: str | None = None) -> str:
    """
    Load a glossary for the given language from the glossary directory.

    Args:
        target_language: Target language code
        glossary_directory: Path to glossary directory

    Returns:
        Glossary content as string, empty if not found or directory not provided
    """
    if not glossary_directory:
        return ""

    glossary_dir_path = Path(glossary_directory)
    if not glossary_dir_path.exists() or not glossary_dir_path.is_dir():
        logger.warning("Glossary directory not found: %s", glossary_dir_path)
        return ""

    glossary_file_path = glossary_dir_path / f"{target_language.lower()}.txt"
    if not glossary_file_path.exists():
        logger.warning(
            "Glossary file not found for language %s: %s",
            target_language,
            glossary_file_path,
        )
        return ""

    return glossary_file_path.read_text(encoding="utf-8-sig").strip()


class TranslationProvider(ABC):
    """Abstract base class for translation providers."""

    def __init__(self, primary_api_key: str):
        """
        Initialize translation provider with API key.

        Args:
            primary_api_key: API key for primary translation service
        """
        self.primary_api_key = primary_api_key

    def translate_srt_with_validation(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_directory: str | None = None,
        input_file_path: Path | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles with timestamp validation.

        Performs translation and validates timestamps. If validation fails,
        retries translation once before failing.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            input_file_path: Path to input file (optional)
            glossary_directory: Path to glossary directory (optional)

        Returns:
            List of translated subtitle objects with validated timestamps

        Raises:
            ValueError: If translation fails validation after all retries
        """
        log = logger.getChild("TranslationProvider")
        path_str = str(input_file_path) if input_file_path else "file"

        log.info(
            "  🌐 Translating %d subtitles to %s for %s...",
            len(subtitle_list),
            target_language,
            path_str,
        )

        for attempt_num in range(1, MAX_SUBTITLE_TRANSLATION_RETRIES + 1):
            try:
                log.info(
                    "  📝 Attempt %d: translation for %s...", attempt_num, path_str
                )

                translated_subtitles = self.translate_subtitles(
                    subtitle_list, target_language, glossary_directory
                )

                log.info(
                    "  🔍 Validating: original=%d, translated=%d subtitles for %s...",
                    len(subtitle_list),
                    len(translated_subtitles),
                    path_str,
                )

                if self._validate_timestamps(subtitle_list, translated_subtitles):
                    log.info("  ✅ Validation successful for %s.", path_str)
                    return translated_subtitles

                log.warning("  ❌ Validation failed for %s, retrying...", path_str)

            except Exception as e:  # noqa: BLE001
                log.warning(
                    "  ❌ Attempt %d failed with error: %s for %s...",
                    attempt_num,
                    e,
                    path_str,
                )

        # All retries failed - fail the task
        log.error(
            "  ❌ All translation attempts failed for %s. Translation cannot proceed.",
            path_str,
        )
        msg = (
            f"Subtitle translation failed after {MAX_SUBTITLE_TRANSLATION_RETRIES} "
            f"attempts - validation failed"
        )
        raise ValueError(msg)

    def _validate_timestamps(
        self, original: list[srt.Subtitle], translated: list[srt.Subtitle]
    ) -> bool:
        """
        Validate that timestamps and cue numbers are preserved.

        Checks for cue count mismatches, index mismatches, timestamp mismatches,
        and blank translations.

        Args:
            original: Original subtitle list
            translated: Translated subtitle list

        Returns:
            True if validation passes, False otherwise
        """
        issues = []
        if len(original) != len(translated):
            issues.append(
                f"Cue count mismatch: original {len(original)}, "
                f"translated {len(translated)}"
            )
        else:
            for i, (orig, trans) in enumerate(zip(original, translated)):
                if orig.index != trans.index:
                    issues.append(
                        f"Cue {i + 1}: index mismatch ({orig.index} vs {trans.index})"
                    )
                if orig.start != trans.start or orig.end != trans.end:
                    issues.append(f"Cue {i + 1}: timestamp mismatch")
                if orig.content.strip() and not trans.content.strip():
                    issues.append(f"Cue {i + 1}: translation is BLANK")

        if issues:
            logger.warning("Translation validation found issues:")
            for issue in issues[:10]:
                logger.warning("  - %s", issue)
            if len(issues) > 10:  # noqa: PLR2004
                logger.warning("  ... and %s more issues", len(issues) - 10)
            return False
        return True

    @abstractmethod
    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_directory: str | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)

        Returns:
            List of translated subtitle objects
        """

    @abstractmethod
    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,
        glossary_directory: str | None = None,
    ) -> str:
        """
        Translate plain text or HTML/XML.

        Args:
            source_text: Text to translate
            target_language: Target language code
            tag_handling: How to handle XML/HTML tags (optional)
            glossary_directory: Path to glossary directory (optional)

        Returns:
            Translated text
        """

    @abstractmethod
    def translate_document(
        self,
        input_file_path: Path,
        output_file_path: Path,
        source_language: str,
        target_language: str,
        glossary_directory: str | None = None,
    ) -> None:
        """
        Translate document file.

        Args:
            input_file_path: Path to input file
            output_file_path: Path to output file
            source_language: Source language code
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)
        """
