"""LLM-based translation providers."""

import logging
import re
from pathlib import Path
from typing import Any

import srt
from django.conf import settings
from litellm import completion

from .base import TranslationProvider, load_glossary

logger = logging.getLogger(__name__)

# Human-readable language names for LLM prompts
LANGUAGE_DISPLAY_NAMES = {
    "en": "English",
    "de": "Deutsch",
    "es": "Español",
    "fr": "Français",
    "pt-br": "Português - Brasil",
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

# LLM error detection keywords
LLM_ERROR_KEYWORDS = [
    "token",
    "quota",
    "limit",
    "too large",
    "context_length_exceeded",
    "503",
    "timeout",
]

# LLM explanation phrases to filter from responses
LLM_EXPLANATION_KEYWORDS = [
    "here is",
    "here's",
    "translation:",
    "translated text:",
    "note:",
    "explanation:",
    "i have translated",
    "i've translated",
]
# Translation markers for structured responses
TRANSLATION_MARKER_START = ":::TRANSLATION_START:::"
TRANSLATION_MARKER_END = ":::TRANSLATION_END:::"


class LLMProvider(TranslationProvider):
    """
    Base class for LLM-based providers (OpenAI, Gemini) that use structured prompting.
    """

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
        timeout: int = settings.LITE_LLM_REQUEST_TIMEOUT,
    ):
        """
        Initialize LLM provider with API keys and model name.

        Args:
            primary_api_key: API key for the LLM service
            repair_api_key: API key for repair service (optional)
            model_name: Name of the LLM model to use
        """
        super().__init__(primary_api_key, repair_api_key)
        self.model_name = model_name
        self.timeout = timeout

    def _get_subtitle_system_prompt(
        self,
        target_language: str,
        glossary_directory: str | None = None,
    ) -> str:
        """
        Generate system prompt for subtitle translation.

        Creates detailed prompts with rules for subtitle translation,
        including glossary terms if provided.

        Args:
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)

        Returns:
            System prompt string for subtitle translation
        """
        target_language_display_name = LANGUAGE_DISPLAY_NAMES.get(
            target_language, target_language
        )

        system_prompt = (
            f"You are a professional subtitle translator. "
            f"Translate the following English subtitles to "
            f"{target_language_display_name}.\n\n"
            "INPUT FORMAT:\n"
            ":::ID:::\n"
            "Text to translate\n\n"
            "OUTPUT FORMAT (exactly):\n"
            ":::ID:::\n"
            "Translated text\n\n"
            "RULES:\n"
            "1. Preserve ALL :::ID::: markers exactly as given.\n"
            "2. Every input ID MUST appear in output with its translation.\n"
            "3. One ID = one translation. "
            "NEVER merge or split content across IDs.\n"
            "4. Keep proper nouns, brand names, and acronyms unchanged.\n"
            "5. Use natural phrasing appropriate for subtitles.\n"
        )

        if glossary_directory:
            glossary_terms = load_glossary(target_language, glossary_directory)
            if glossary_terms:
                system_prompt += (
                    f"\nGLOSSARY TERMS (use these translations):\n{glossary_terms}\n"
                )

        return system_prompt

    def _get_text_system_prompt(
        self,
        target_language: str,
        glossary_directory: str | None = None,
    ) -> str:
        """
        Generate system prompt for text/HTML/XML translation.

        Creates detailed prompts with rules for text translation,
        including glossary terms if provided.

        Args:
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)

        Returns:
            System prompt string for text translation
        """
        target_language_display_name = LANGUAGE_DISPLAY_NAMES.get(
            target_language, target_language
        )

        system_prompt = (
            f"You are a professional translator. "
            f"Translate the following English text to "
            f"{target_language_display_name}.\n\n"
            f"OUTPUT FORMAT (exactly):\n"
            f"{TRANSLATION_MARKER_START}\n"
            "Your translated text here\n"
            f"{TRANSLATION_MARKER_END}\n\n"
            "CRITICAL RULES FOR XML/HTML TAGS:\n"
            "1. NEVER translate or modify XML/HTML tag names or structure.\n"
            "2. XML/HTML tags include anything within angle brackets: < >.\n"
            "3. Preserve ALL tags exactly as they appear in the input.\n"
            "4. Only translate:\n"
            "   a) Visible TEXT CONTENT between tags, AND\n"
            "   b) User-facing / human-readable attribute VALUES listed below.\n\n"
            
            "USER-FACING ATTRIBUTES THAT MUST BE TRANSLATED (when present):\n"
            "   - placeholder\n"
            "   - title\n"
            "   - aria-label\n"
            "   - alt\n"
            "   - label\n"
            "   - value (ONLY if it is clearly user-visible text, not a key or code)\n"
            "   - display_name\n\n"
            
            "ATTRIBUTES THAT MUST NEVER BE TRANSLATED OR MODIFIED:\n"
            "   - id, class, name\n"
            "   - href, src, action\n"
            "   - data-*, aria-* (except aria-label)\n"
            "   - role, type, rel, target\n"
            "   - url_name, filename, correct (except as noted below)\n"
            "   - JavaScript hooks, CSS selectors, analytics identifiers\n\n"
            
            "5. Attribute NAMES must NEVER be translated — only approved attribute VALUES.\n"
            "6. DO NOT add new attributes or remove existing ones.\n"
            "7. DO NOT translate attribute values that look like:\n"
            "   - URLs, file paths, IDs, keys, slugs, or code\n"
            "8. DO NOT translate self-closing or structural tags.\n\n"
            
            "OPEN EDX–SPECIFIC RULES:\n"
            "1. Translate 'options' and 'correct' attribute VALUES in 'optioninput' tags ONLY.\n"
            "2. DO NOT translate 'correct' anywhere else.\n"
            "3. DO NOT add display_name if it is missing.\n\n"
            
            "EXAMPLES OF WHAT NOT TO TRANSLATE:\n"
            "   - <video>, <problem>, <html>, <div>, <p>, etc.\n"
            "   - Attributes: url_name, filename, src, href, class\n"
            "   - Self-closing tags: <vertical />, <sequential />\n\n"
            
            "GENERAL TRANSLATION RULES:\n"
            "1. Output ONLY the translation between the markers.\n"
            "2. Maintain the original formatting, spacing, line breaks, and indentation.\n"
            "3. Keep proper nouns, brand names, acronyms, and product names unchanged.\n"
            "4. Do NOT include explanations, notes, or commentary.\n"
            "5. Ensure the output is valid XML/HTML after translation.\n"
        )

        if glossary_directory:
            glossary_terms = load_glossary(target_language, glossary_directory)
            if glossary_terms:
                system_prompt += (
                    f"\nGLOSSARY TERMS (use these translations):\n{glossary_terms}\n"
                )

        return system_prompt

    def _parse_structured_response(
        self, llm_response_text: str, original_subtitle_batch: list[srt.Subtitle]
    ) -> list[srt.Subtitle]:
        """
        Parse the structured response and map back to original blocks.

        Extracts translated content from LLM response using ID markers and maps
        back to original subtitle objects preserving timestamps.

        Args:
            llm_response_text: Raw response text from LLM
            original_subtitle_batch: Original subtitle batch for reference

        Returns:
            List of parsed subtitle objects with translations
        """
        parsed_subtitle_list = []

        subtitle_id_pattern = re.compile(
            r":::(\d+):::\s*(.*?)(?=(?::::\d+:::|$))", re.DOTALL
        )
        subtitle_matches = subtitle_id_pattern.findall(llm_response_text)

        translation_map = {}
        for subtitle_id_str, translated_text in subtitle_matches:
            clean_subtitle_id = subtitle_id_str.strip()
            translation_map[clean_subtitle_id] = translated_text.strip()

        for original_subtitle in original_subtitle_batch:
            subtitle_id_key = str(original_subtitle.index)
            if subtitle_id_key in translation_map:
                parsed_subtitle_list.append(
                    srt.Subtitle(
                        index=original_subtitle.index,
                        start=original_subtitle.start,
                        end=original_subtitle.end,
                        content=translation_map[subtitle_id_key],
                    )
                )
            else:
                logger.warning(
                    "Block %s missing in translation response. Leaving empty.",
                    subtitle_id_key,
                )
                parsed_subtitle_list.append(
                    srt.Subtitle(
                        index=original_subtitle.index,
                        start=original_subtitle.start,
                        end=original_subtitle.end,
                        content="",
                    )
                )

        return parsed_subtitle_list

    def _parse_text_response(self, llm_response_text: str) -> str:
        """
        Parse the structured text translation response.

        Extracts translated content between translation markers, filtering out
        explanations and metadata.

        Args:
            llm_response_text: Raw response text from LLM

        Returns:
            Cleaned translated text
        """
        # Try to extract content between markers
        start_idx = llm_response_text.find(TRANSLATION_MARKER_START)
        end_idx = llm_response_text.find(TRANSLATION_MARKER_END)

        if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
            # Extract content between markers
            translated_content = llm_response_text[
                start_idx + len(TRANSLATION_MARKER_START) : end_idx
            ]
            return translated_content.strip()

        # Fallback: if markers not found, try to extract without explanation
        lines = llm_response_text.split("\n")
        filtered_lines = []
        skip_explanation = False

        for line in lines:
            lower_line = line.lower().strip()
            # Skip lines that look like explanations
            if any(phrase in lower_line for phrase in LLM_EXPLANATION_KEYWORDS):
                skip_explanation = True
                continue

            # If we hit the translation markers in any form, start including
            if TRANSLATION_MARKER_START.lower() in lower_line:
                skip_explanation = False
                continue

            if TRANSLATION_MARKER_END.lower() in lower_line:
                break

            if not skip_explanation and line.strip():
                filtered_lines.append(line)

        result = "\n".join(filtered_lines).strip()

        # If we still have no result, return the original response
        return result if result else llm_response_text.strip()

    def _call_llm(
        self, system_prompt: str, user_content: str, **additional_kwargs: Any
    ) -> str:
        """
        Call the LLM API with system and user prompts.

        Args:
            system_prompt: System prompt defining LLM behavior
            user_content: User content to translate
            **additional_kwargs: Additional arguments for the API call

        Returns:
            LLM response content as string
        """
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        llm_response = completion(
            model=self.model_name,
            messages=llm_messages,
            api_key=self.primary_api_key,
            timeout=self.timeout,
            **additional_kwargs,
        )
        return llm_response.choices[0].message.content.strip()

    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_directory: str | None = None,
    ) -> list[srt.Subtitle]:
        """
        Translate subtitles using LLM.

        Processes subtitles in batches with dynamic batch sizing to handle API limits.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)

        Returns:
            List of translated subtitle objects
        """
        system_prompt = self._get_subtitle_system_prompt(
            target_language, glossary_directory
        )

        translated_subtitle_list = []
        current_batch_size = len(subtitle_list)

        current_index = 0
        retry_count = 0
        max_retries = 3

        while current_index < len(subtitle_list):
            subtitle_batch = subtitle_list[
                current_index : current_index + current_batch_size
            ]

            user_payload_parts = []
            for subtitle_item in subtitle_batch:
                user_payload_parts.append(f":::{subtitle_item.index}:::")
                user_payload_parts.append(subtitle_item.content)
                user_payload_parts.append("")
            user_payload = "\n".join(user_payload_parts)

            logger.info(
                "  Translating batch starting at ID %s (%s blocks)...",
                subtitle_batch[0].index,
                len(subtitle_batch),
            )

            try:
                llm_response_text = self._call_llm(system_prompt, user_payload)
                translated_batch = self._parse_structured_response(
                    llm_response_text, subtitle_batch
                )
                translated_subtitle_list.extend(translated_batch)
                current_index += current_batch_size
                retry_count = 0  # Reset retry count on success

            except Exception as llm_error:
                error_message = str(llm_error).lower()
                if any(
                    error_term in error_message for error_term in LLM_ERROR_KEYWORDS
                ):
                    if current_batch_size <= 1 or retry_count >= max_retries:
                        logger.exception(
                            "Failed after %s batch size reduction attempts", retry_count
                        )
                        raise

                    logger.warning(
                        "Error: %s. Reducing batch size (attempt %s/%s)...",
                        llm_error,
                        retry_count + 1,
                        max_retries,
                    )
                    current_batch_size = max(1, current_batch_size // 2)
                    retry_count += 1
                    continue
                else:
                    raise

        return translated_subtitle_list

    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,  # noqa: ARG002
        glossary_directory: str | None = None,
    ) -> str:
        """
        Translate text using LLM.

        Handles plain text, HTML, and XML content with appropriate prompting.

        Args:
            source_text: Text to translate
            target_language: Target language code
            tag_handling: How to handle XML/HTML tags (not used for LLM)
            glossary_directory: Path to glossary directory (optional)

        Returns:
            Translated text
        """
        if not source_text or not source_text.strip():
            return source_text

        system_prompt = self._get_text_system_prompt(
            target_language, glossary_directory
        )

        try:
            llm_response = self._call_llm(system_prompt, source_text)
            logger.info(
                "\n\n\nSource Text:\n%s\n LLM Response:\n%s\n\n",
                source_text,
                llm_response,
            )
            return self._parse_text_response(llm_response)
        except (ValueError, ConnectionError) as llm_error:
            logger.warning("LLM translation failed: %s", llm_error)
            return source_text

    def translate_document(
        self,
        input_file_path: Path,
        output_file_path: Path,
        source_language: str,  # noqa: ARG002
        target_language: str,
        glossary_directory: str | None = None,
    ) -> None:
        """
        Translate document by reading and translating content.

        Handles SRT files using subtitle translation and other files as text.

        Args:
            input_file_path: Path to input file
            output_file_path: Path to output file
            source_language: Source language code (not used)
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)
        """
        # For SRT files, use subtitle translation
        if input_file_path.suffix == ".srt":
            srt_content = input_file_path.read_text(encoding="utf-8")
            subtitle_list = list(srt.parse(srt_content))

            translated_subtitle_list = self.translate_srt_with_validation(
                subtitle_list, target_language, glossary_directory
            )

            translated_srt_content = srt.compose(translated_subtitle_list)
            output_file_path.write_text(translated_srt_content, encoding="utf-8")
        else:
            # For other files, treat as text
            file_content = input_file_path.read_text(encoding="utf-8")
            translated_file_content = self.translate_text(
                file_content, target_language, glossary_directory=glossary_directory
            )
            output_file_path.write_text(translated_file_content, encoding="utf-8")


class OpenAIProvider(LLMProvider):
    """OpenAI translation provider."""

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
        """
        Initialize OpenAI provider.

        Args:
            primary_api_key: OpenAI API key
            repair_api_key: API key for repair service (optional)
            model_name: OpenAI model name (e.g., "gpt-5.2")

        Raises:
            ValueError: If model_name is not provided
        """
        if not model_name:
            msg = "model_name is required for OpenAIProvider"
            raise ValueError(msg)
        super().__init__(primary_api_key, repair_api_key, f"openai/{model_name}")

    def _call_llm(
        self, system_prompt: str, user_content: str, **additional_kwargs: Any
    ) -> str:
        """
        Call OpenAI API with prompts.

        Args:
            system_prompt: System prompt defining behavior
            user_content: User content to translate
            **additional_kwargs: Additional arguments for the API

        Returns:
            OpenAI response content
        """
        return super()._call_llm(system_prompt, user_content, **additional_kwargs)


class GeminiProvider(LLMProvider):
    """Gemini translation provider."""

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
        """
        Initialize Gemini provider.

        Args:
            primary_api_key: Gemini API key
            repair_api_key: API key for repair service (optional)
            model_name: Gemini model name (e.g., "gemini-3-pro-preview")

        Raises:
            ValueError: If model_name is not provided
        """
        if not model_name:
            msg = "model_name is required for GeminiProvider"
            raise ValueError(msg)
        super().__init__(primary_api_key, repair_api_key, f"gemini/{model_name}")


class MistralProvider(LLMProvider):
    """Mistral translation provider."""

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
        """
        Initialize Mistral provider.

        Args:
            primary_api_key: Mistral API key
            repair_api_key: API key for repair service (optional)
            model_name: Mistral model name (e.g., "mistral-large-latest")

        Raises:
            ValueError: If model_name is not provided
        """
        if not model_name:
            msg = "model_name is required for MistralProvider"
            raise ValueError(msg)
        super().__init__(primary_api_key, repair_api_key, f"mistral/{model_name}")
