"""Base classes for translation providers."""

import logging
import re
from abc import ABC, abstractmethod
from pathlib import Path

import srt

logger = logging.getLogger(__name__)

MAX_SUBTITLE_TRANSLATION_RETRIES = 1


def parse_glossary_text(glossary_text: str) -> dict[str, str]:
    """
    Parse a glossary text blob into a dict[term, translation].

    Supports lines like:
      - 'term' -> 'translation'
    Ignores comments/blank lines and preserves original (un-normalized) strings.
    """
    if not glossary_text:
        return {}

    out: dict[str, str] = {}
    for raw_line in glossary_text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        # Bullet prefix is optional
        if line.startswith("-"):
            line = line[1:].strip()

        # Split on the first arrow only
        if "->" not in line:
            continue
        left, right = (part.strip() for part in line.split("->", 1))
        if not left or not right:
            continue

        # Strip optional wrapping quotes
        left = left.strip("'\"").strip()
        right = right.strip("'\"").strip()
        if left:
            out[left] = right

    return out


def _normalize_for_match(value: str) -> str:
    """
    Normalize for matching:
    - trim outer whitespace
    - case-insensitive
    - collapse all whitespace runs (incl newlines) to a single space
    """
    # Collapse whitespace so multi-word glossary terms match across line breaks.
    return re.sub(r"\s+", " ", (value or "").strip().lower())


def filter_glossary_for_subtitles(
    subtitles: list[srt.Subtitle],
    glossary: dict[str, str],
) -> dict[str, str]:
    """
    Return only glossary entries whose terms appear in subtitle content.

    Matching rules:
    - case-insensitive
    - trims whitespace
    - collapses whitespace (so phrases match across subtitle newlines)
    - avoids partial-word false positives via non-word boundaries
      (e.g. 'art' won't match 'cart')
    """
    if not subtitles or not glossary:
        return {}

    # Efficient: join once, normalize once.
    corpus = _normalize_for_match(" ".join((s.content or "") for s in subtitles))
    if not corpus:
        return {}

    # Compile patterns once per glossary entry (helps for large glossaries).
    compiled: list[tuple[str, str, re.Pattern[str]]] = []
    for term, translation in glossary.items():
        norm_term = _normalize_for_match(term)
        if not norm_term:
            continue
        compiled.append(
            (
                term,
                translation,
                re.compile(rf"(?<!\w){re.escape(norm_term)}(?!\w)"),
            )
        )

    return {term: translation for term, translation, pattern in compiled if pattern.search(corpus)}


def format_glossary_for_prompt(glossary: dict[str, str]) -> str:
    """
    Format a dict glossary to prompt-friendly lines.
    Keeps original keys/values; returns "" if empty.
    """
    if not glossary:
        return ""
    return "\n".join(f"- '{k}' -> '{v}'" for k, v in glossary.items())


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


def load_glossary_dict(
    target_language: str, glossary_directory: str | None = None
) -> dict[str, str]:
    """
    Load and parse the glossary file for a language into a dict.
    """
    return parse_glossary_text(load_glossary(target_language, glossary_directory))


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
