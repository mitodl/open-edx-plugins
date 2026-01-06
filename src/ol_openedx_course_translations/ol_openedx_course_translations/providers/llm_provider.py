"""LLM-based translation providers."""

import logging
import re
from pathlib import Path
from typing import Any

import srt
from litellm import completion

from ol_openedx_course_translations.utils.constants import (
    LANGUAGE_DISPLAY_NAMES,
    LLM_ERROR_KEYWORDS,
    LLM_EXPLANATION_KEYWORDS,
    TRANSLATION_MARKER_END,
    TRANSLATION_MARKER_START,
)

from .base import TranslationProvider, load_glossary

logger = logging.getLogger(__name__)


class LLMProvider(TranslationProvider):
    """
    Base class for LLM-based providers (OpenAI, Gemini) that use structured prompting.
    """

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
        super().__init__(primary_api_key, repair_api_key)
        self.model_name = model_name

    def _get_system_prompt(
        self,
        target_language: str,
        content_type: str = "subtitle",
        glossary_file: str | None = None,
    ) -> str:
        target_language_display_name = LANGUAGE_DISPLAY_NAMES.get(
            target_language, target_language
        )

        if content_type == "subtitle":
            system_prompt_template = (
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
        else:
            system_prompt_template = (
                f"You are a professional translator. "
                f"Translate the following English text to "
                f"{target_language_display_name}.\n\n"
                f"OUTPUT FORMAT (exactly):\n"
                f"{TRANSLATION_MARKER_START}\n"
                "Your translated text here\n"
                f"{TRANSLATION_MARKER_END}\n\n"
                "CRITICAL RULES FOR XML/HTML TAGS:\n"
                "1. NEVER translate or modify XML/HTML tags, tag names, or attributes except display_name.\n"  # noqa: E501
                "2. XML/HTML tags include anything within angle brackets: < >.\n"
                '3. Tag attributes (name="value") must remain in English.\n'
                "4. Only translate the TEXT CONTENT between tags.\n"
                "5. Preserve ALL tags exactly as they appear in the input.\n"
                "6. Examples of what NOT to translate:\n"
                "   - <video>, <problem>, <html>, <div>, <p>, etc.\n"
                "   - Attributes: url_name, filename, src, etc.\n"
                "   - Self-closing tags: <vertical />, <sequential />\n\n"
                "GENERAL TRANSLATION RULES:\n"
                "1. Output ONLY the translation between the markers.\n"
                "2. Maintain the original formatting and structure.\n"
                "3. Keep proper nouns, brand names, and acronyms unchanged.\n"
                "4. Do NOT include explanations, notes, or commentary.\n"
                "5. Preserve spacing, line breaks, and indentation.\n"
            )

        if glossary_file:
            glossary_terms = load_glossary(target_language, glossary_file)
            if glossary_terms:
                system_prompt_template += (
                    f"\nGLOSSARY TERMS (use these translations):\n{glossary_terms}\n"
                )

        return system_prompt_template

    def _parse_structured_response(
        self, llm_response_text: str, original_subtitle_batch: list[srt.Subtitle]
    ) -> list[srt.Subtitle]:
        """Parse the structured response and map back to original blocks."""
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
        """Parse the structured text translation response."""
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
        llm_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]
        llm_response = completion(
            model=self.model_name,
            messages=llm_messages,
            api_key=self.primary_api_key,
            **additional_kwargs,
        )
        return llm_response.choices[0].message.content.strip()

    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_file: str | None = None,
    ) -> list[srt.Subtitle]:
        """Translate subtitles using LLM."""
        system_prompt = self._get_system_prompt(
            target_language, "subtitle", glossary_file
        )

        translated_subtitle_list = []
        current_batch_size = len(subtitle_list)

        current_index = 0
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

            except Exception as llm_error:
                error_message = str(llm_error).lower()
                if any(
                    error_term in error_message for error_term in LLM_ERROR_KEYWORDS
                ):
                    if current_batch_size <= 1:
                        logger.exception("Failed even with batch size 1")
                        raise

                    logger.warning("Error: %s. Reducing batch size...", llm_error)
                    current_batch_size = max(1, current_batch_size // 2)
                    continue
                else:
                    raise

        return translated_subtitle_list

    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,  # noqa: ARG002
        glossary_file: str | None = None,
    ) -> str:
        """Translate text using LLM."""
        if not source_text or not source_text.strip():
            return source_text

        system_prompt = self._get_system_prompt(target_language, "text", glossary_file)

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
    ) -> None:
        """Translate document by reading and translating content."""
        # For SRT files, use subtitle translation
        if input_file_path.suffix == ".srt":
            srt_content = input_file_path.read_text(encoding="utf-8")
            subtitle_list = list(srt.parse(srt_content))

            translated_subtitle_list = self.translate_subtitles(
                subtitle_list, target_language
            )

            translated_srt_content = srt.compose(translated_subtitle_list)
            output_file_path.write_text(translated_srt_content, encoding="utf-8")
        else:
            # For other files, treat as text
            file_content = input_file_path.read_text(encoding="utf-8")
            translated_file_content = self.translate_text(file_content, target_language)
            output_file_path.write_text(translated_file_content, encoding="utf-8")


class OpenAIProvider(LLMProvider):
    """OpenAI translation provider."""

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
        if not model_name:
            msg = "model_name is required for OpenAIProvider"
            raise ValueError(msg)
        super().__init__(primary_api_key, repair_api_key, f"openai/{model_name}")

    def _call_llm(
        self, system_prompt: str, user_content: str, **additional_kwargs: Any
    ) -> str:
        return super()._call_llm(system_prompt, user_content, **additional_kwargs)


class GeminiProvider(LLMProvider):
    """Gemini translation provider."""

    def __init__(
        self,
        primary_api_key: str,
        repair_api_key: str | None = None,
        model_name: str | None = None,
    ):
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
        if not model_name:
            msg = "model_name is required for MistralProvider"
            raise ValueError(msg)
        super().__init__(primary_api_key, repair_api_key, f"mistral/{model_name}")
