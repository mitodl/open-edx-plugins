"""Base classes for translation providers."""

import logging
import math
from abc import ABC, abstractmethod
from pathlib import Path

import srt
from django.conf import settings
from litellm import completion

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
            repair_api_key: API key for repair service
                (optional, used for subtitle repair)
        """
        self.primary_api_key = primary_api_key
        self.repair_api_key = repair_api_key

    def translate_srt_with_validation(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_file: str | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles with timestamp validation and repair.

        Performs translation, validates timestamps, and attempts repair
        if validation fails.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_file: Path to glossary directory (optional)

        Returns:
            List of translated subtitle objects with validated timestamps

        Raises:
            ValueError: If timestamp repair fails after validation
        """
        log = logger.getChild("TranslationProvider")
        log.info("  🌐 Translating subtitles to %s...", target_language)

        # Try translation with retries
        translated_subtitles = []
        for attempt in range(MAX_SUBTITLE_TRANSLATION_RETRIES + 1):
            if attempt > 0:
                log.info("  🔧 Retrying subtitle translations...")

            translated_subtitles = self.translate_subtitles(
                subtitle_list, target_language, glossary_file
            )

            log.info(
                "  🔍 %sValidating translated subtitles...",
                "Re-" if attempt > 0 else "",
            )

            if self._validate_timestamps(subtitle_list, translated_subtitles):
                log.info(
                    "  ✅ Timestamps validated successfully%s.",
                    " on retry" if attempt > 0 else "",
                )
                return translated_subtitles

            log.warning(
                "  ❌ Timestamp %svalidation failed.", "re-" if attempt > 0 else ""
            )

        repaired_subtitles = self._repair_timestamps_with_llm(
            subtitle_list, translated_subtitles, target_language
        )

        log.info("  🔍 Re-validating repaired subtitles...")
        if self._validate_timestamps(subtitle_list, repaired_subtitles):
            log.info("  ✅ Timestamps repaired and validated successfully.")
            return repaired_subtitles

        log.error("  ❌ Timestamp repair failed. Translation cannot proceed.")
        raise ValueError(  # noqa: TRY003
            "Subtitle timestamp repair failed - timestamps could not be validated"  # noqa: EM101
        )

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

    def _repair_timestamps_with_llm(
        self,
        original: list[srt.Subtitle],
        misaligned: list[srt.Subtitle],
        target_lang: str,
    ) -> list[srt.Subtitle]:
        """
        Repair misaligned timestamps using LLM via litellm.

        Processes subtitles in batches, using an LLM to realign translated content
        with original timestamps.

        Args:
            original: Original subtitle list with correct timestamps
            misaligned: Translated subtitle list with incorrect timestamps
            target_lang: Target language code

        Returns:
            List of repaired subtitles with corrected timestamps
        """
        if not self.repair_api_key:
            logger.warning("   No repair API key available, skipping repair.")
            return misaligned

        logger.info("  🔧 Repairing timestamps using LLM...")

        repaired_subtitles = []
        batch_size = 50
        total_batches = math.ceil(len(original) / batch_size)

        for i in range(total_batches):
            start = i * batch_size
            end = min(len(original), start + batch_size)
            original_batch = original[start:end]

            # Get corresponding translated batch with overlap
            overlap = 5
            t_start = max(0, start - overlap)
            t_end = min(len(misaligned), end + overlap)
            misaligned_batch = misaligned[t_start:t_end]

            original_text = srt.compose(original_batch)
            misaligned_text = srt.compose(misaligned_batch)

            logger.info("  Repairing chunk %s/%s...", i + 1, total_batches)

            system_prompt = (
                f"You repair timestamp alignment problems in SRT subtitles "
                f"translated to {target_lang}.\n"
                "Each request contains a subset of the original SRT and the "
                "corresponding translated output.\n"
                "For the cues shown, copy the cue numbers and timestamps EXACTLY "
                "from the original section\n"
                "and rewrite the translated text so it aligns 1:1 with those cues.\n"
                "Return only a valid SRT segment for the provided cues."
            )

            user_prompt = (
                f"You are fixing cues {original_batch[0].index}-"
                f"{original_batch[-1].index}.\n\n"
                "ORIGINAL ENGLISH SRT WITH CORRECT TIMESTAMPS:\n"
                "```\n"
                f"{original_text}\n"
                "```\n\n"
                "TRANSLATED SRT WITH INCORRECT TIMESTAMPS:\n"
                "```\n"
                f"{misaligned_text}\n"
                "```\n\n"
                "Return ONLY the corrected SRT for the cues shown in the "
                "original section."
            )

            try:
                response = completion(
                    model=f"openai/{settings.TRANSLATIONS_PROVIDERS['openai']['default_model']}",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    api_key=self.repair_api_key,
                    temperature=0.0,
                )

                content = response.choices[0].message.content.strip()

                # Remove markdown code blocks if present
                if content.startswith("```"):
                    lines = content.splitlines()
                    if lines[0].startswith("```"):
                        lines.pop(0)
                    if lines and lines[-1].startswith("```"):
                        lines.pop()
                    content = "\n".join(lines)

                repaired_batch = list(srt.parse(content))
                repaired_subtitles.extend(repaired_batch)

            except Exception as e:  # noqa: BLE001
                logger.error("  Failed to repair batch %s: %s", i + 1, e)  # noqa: TRY400
                # Fallback: use original timestamps with empty text to preserve structure  # noqa: E501
                for sub in original_batch:
                    repaired_subtitles.append(  # noqa: PERF401
                        srt.Subtitle(
                            index=sub.index,
                            start=sub.start,
                            end=sub.end,
                            content="",
                        )
                    )

        return repaired_subtitles

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
