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

    def __init__(self, primary_api_key: str, repair_api_key: str | None = None):
        """
        Initialize translation provider with API keys.

        Args:
            primary_api_key: API key for primary translation service
            repair_api_key: API key for repair service (DeepL API key)
        """
        self.primary_api_key = primary_api_key
        self.repair_api_key = repair_api_key

    def translate_srt_with_validation(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_file: str | None = None,
        input_file_path: Path | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles with timestamp validation and repair.

        Performs translation, validates timestamps, and attempts repair
        if validation fails using DeepL.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_file: Path to glossary directory (optional)
            input_file_path: Path to input file (optional)

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
                    subtitle_list, target_language, glossary_file
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

        # All retries failed - try DeepL repair as last resort
        log.info("  🔧 All attempts failed, trying DeepL repair for %s...", path_str)
        repaired_subtitles = self._repair_timestamps_with_deepl(
            subtitle_list, target_language
        )

        log.info("  🔍 Re-validating repaired subtitles for %s...", path_str)
        if self._validate_timestamps(subtitle_list, repaired_subtitles):
            log.info(
                "  ✅ Timestamps repaired and validated successfully for %s.", path_str
            )
            return repaired_subtitles

        log.error(
            "  ❌ Timestamp repair failed for %s. Translation cannot proceed.", path_str
        )
        msg = "Subtitle timestamp repair failed - timestamps could not be validated"
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

    def _repair_timestamps_with_deepl(
        self,
        original: list[srt.Subtitle],
        target_lang: str,
    ) -> list[srt.Subtitle]:
        """
        Repair misaligned timestamps using DeepL translation.

        Uses DeepL to retranslate subtitles with proper timestamp preservation.

        Args:
            original: Original subtitle list with correct timestamps
            target_lang: Target language code

        Returns:
            List of repaired subtitles with corrected timestamps
        """
        if not self.repair_api_key:
            logger.warning("   No repair API key available, skipping repair.")
            return original

        logger.info("  🔧 Repairing timestamps using DeepL...")

        try:
            # Import DeepL provider for repair
            from ol_openedx_course_translations.providers.deepl_provider import (  # noqa: PLC0415
                DeepLProvider,
            )

            # Create DeepL provider instance for repair
            deepl_provider = DeepLProvider(self.repair_api_key, None)

            # Use DeepL to translate with proper timestamp preservation
            repaired_subtitles = deepl_provider.translate_subtitles(
                original, target_lang, None
            )

            logger.info("  ✅ DeepL repair completed.")
            return repaired_subtitles  # noqa: TRY300

        except Exception as e:  # noqa: BLE001
            logger.error("  ❌ DeepL repair failed: %s", e)  # noqa: TRY400
            # Fallback: return original with empty content to preserve structure
            return [
                srt.Subtitle(
                    index=sub.index,
                    start=sub.start,
                    end=sub.end,
                    content="",
                )
                for sub in original
            ]

    @abstractmethod
    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_file: str | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_file: Path to glossary directory (optional)

        Returns:
            List of translated subtitle objects
        """

    @abstractmethod
    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,
        glossary_file: str | None = None,
    ) -> str:
        """
        Translate plain text or HTML/XML.

        Args:
            source_text: Text to translate
            target_language: Target language code
            tag_handling: How to handle XML/HTML tags (optional)
            glossary_file: Path to glossary directory (optional)

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
        glossary_file: str | None = None,
    ) -> None:
        """
        Translate document file.

        Args:
            input_file_path: Path to input file
            output_file_path: Path to output file
            source_language: Source language code
            target_language: Target language code
            glossary_file: Path to glossary directory (optional)
        """
