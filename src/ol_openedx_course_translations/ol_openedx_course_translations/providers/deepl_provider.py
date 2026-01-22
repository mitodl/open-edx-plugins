"""DeepL translation provider."""

import logging
import re
from pathlib import Path

import deepl
import srt

from .base import TranslationProvider

logger = logging.getLogger(__name__)

# DeepL API constants
DEEPL_MAX_PAYLOAD_SIZE = 128000  # 128KB limit
DEEPL_ENABLE_BETA_LANGUAGES = True
# Language code mappings for DeepL API
DEEPL_LANGUAGE_CODES = {
    "fr": "FR",
    "de": "DE",
    "es-419": "ES-419",
    "es": "ES-419",
    "es-ES": "ES",
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


def _check_payload_size(payload: str) -> None:
    """
    Check if payload size exceeds DeepL API limits.

    Args:
        payload: Payload string to check

    Raises:
        ValueError: If payload exceeds 128KB limit
    """
    if len(payload.encode("utf-8")) > DEEPL_MAX_PAYLOAD_SIZE:
        msg = "Payload too large for DeepL API"
        raise ValueError(msg)


def _validate_batch_response(xml_matches: list, subtitle_batch: list) -> None:
    """
    Validate that DeepL returned the expected number of items.

    Args:
        xml_matches: List of XML matches from DeepL response
        subtitle_batch: Original subtitle batch

    Raises:
        ValueError: If counts don't match
    """
    if len(xml_matches) != len(subtitle_batch):
        logger.warning(
            "DeepL returned %d items, expected %d. Retrying with smaller batch.",
            len(xml_matches),
            len(subtitle_batch),
        )
        msg = "Count mismatch in DeepL response"
        raise ValueError(msg)


class DeepLProvider(TranslationProvider):
    """DeepL translation provider."""

    def __init__(self, primary_api_key: str, repair_api_key: str | None = None):
        """
        Initialize DeepL provider.

        Args:
            primary_api_key: DeepL API key
            repair_api_key: API key for repair service (optional)
        """
        super().__init__(primary_api_key, repair_api_key)
        self.deepl_translator = deepl.Translator(auth_key=primary_api_key)

    def translate_subtitles(
        self,
        subtitle_list: list[srt.Subtitle],
        target_language: str,
        glossary_directory: str | None = None,  # noqa: ARG002
    ) -> list[srt.Subtitle]:
        """
        Translate SRT subtitles using DeepL.

        Uses XML tag handling to preserve subtitle structure and timestamps.
        Implements dynamic batch sizing to handle API limits.

        Args:
            subtitle_list: List of subtitle objects to translate
            target_language: Target language code
            glossary_directory: Path to glossary directory (not used by DeepL)

        Returns:
            List of translated subtitle objects

        Raises:
            ValueError: If target language is not supported by DeepL
        """
        deepl_target_code = DEEPL_LANGUAGE_CODES.get(target_language.lower())
        if not deepl_target_code:
            error_msg = f"DeepL does not support language '{target_language}'."
            raise ValueError(error_msg)

        deepl_extra_params = {"enable_beta_languages": DEEPL_ENABLE_BETA_LANGUAGES}

        translated_subtitle_list = []
        current_batch_size = len(subtitle_list)

        current_index = 0
        while current_index < len(subtitle_list):
            subtitle_batch = subtitle_list[
                current_index : current_index + current_batch_size
            ]
            logger.info(
                "  Translating batch starting at ID %s (%s blocks)...",
                subtitle_batch[0].index,
                len(subtitle_batch),
            )

            try:
                # Construct XML payload
                xml_payload_parts = ["<d>"]
                for subtitle_item in subtitle_batch:
                    xml_safe_content = (
                        subtitle_item.content.replace("&", "&amp;")
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )
                    xml_payload_parts.append(
                        f'<s i="{subtitle_item.index}">{xml_safe_content}</s>'
                    )
                xml_payload_parts.append("</d>")
                xml_payload = "".join(xml_payload_parts)

                _check_payload_size(xml_payload)

                translation_result = self.deepl_translator.translate_text(
                    xml_payload,
                    source_lang="EN",
                    target_lang=deepl_target_code,
                    preserve_formatting=True,
                    tag_handling="xml",
                    split_sentences="nonewlines",
                    extra_body_parameters=deepl_extra_params,
                )

                translated_xml_content = translation_result.text

                # Parse XML back
                subtitle_pattern = re.compile(r'<s i="(\d+)">(.*?)</s>', re.DOTALL)
                xml_matches = subtitle_pattern.findall(translated_xml_content)

                _validate_batch_response(xml_matches, subtitle_batch)

                subtitle_index_map = {str(sub.index): sub for sub in subtitle_batch}

                for subtitle_index_str, translated_content in xml_matches:
                    # Unescape XML entities
                    unescaped_content = (
                        translated_content.replace("&lt;", "<")
                        .replace("&gt;", ">")
                        .replace("&amp;", "&")
                    )

                    if subtitle_index_str in subtitle_index_map:
                        original_subtitle = subtitle_index_map[subtitle_index_str]
                        translated_subtitle_list.append(
                            srt.Subtitle(
                                index=original_subtitle.index,
                                start=original_subtitle.start,
                                end=original_subtitle.end,
                                content=unescaped_content.strip(),
                            )
                        )

                current_index += current_batch_size

            except Exception as translation_error:
                if current_batch_size <= 1:
                    logger.exception("Failed even with batch size 1")
                    raise

                logger.warning("  Error: %s. Reducing batch size...", translation_error)
                current_batch_size = max(1, current_batch_size // 2)
                continue

        return translated_subtitle_list

    def translate_text(
        self,
        source_text: str,
        target_language: str,
        tag_handling: str | None = None,
        glossary_directory: str | None = None,  # noqa: ARG002
    ) -> str:
        """
        Translate text using DeepL.

        Args:
            source_text: Text to translate
            target_language: Target language code
            tag_handling: How to handle XML/HTML tags ("xml" or "html")
            glossary_directory: Path to glossary directory (not used by DeepL)

        Returns:
            Translated text, or original text if translation fails

        Raises:
            ValueError: If target language is not supported by DeepL
        """
        if not source_text or not source_text.strip():
            return source_text

        deepl_target_code = DEEPL_LANGUAGE_CODES.get(target_language.lower())
        if not deepl_target_code:
            error_msg = f"DeepL does not support language '{target_language}'."
            raise ValueError(error_msg)

        try:
            translation_result = self.deepl_translator.translate_text(
                source_text,
                source_lang="EN",
                target_lang=deepl_target_code,
                tag_handling=tag_handling,
            )
        except deepl.exceptions.DeepLException as deepl_error:
            logger.warning("DeepL translation failed: %s", deepl_error)
            return source_text
        else:
            return translation_result.text

    def translate_document(
        self,
        input_file_path: Path,
        output_file_path: Path,
        source_language: str,
        target_language: str,
        glossary_directory: str | None = None,
    ) -> None:
        """
        Translate document using DeepL.

        For SRT files, uses subtitle translation. For other files, uses DeepL's
        document translation API.

        Args:
            input_file_path: Path to input file
            output_file_path: Path to output file
            source_language: Source language code
            target_language: Target language code
            glossary_directory: Path to glossary directory (optional)

        Raises:
            ValueError: If target language is not supported by DeepL
        """
        deepl_target_code = DEEPL_LANGUAGE_CODES.get(target_language.lower())
        if not deepl_target_code:
            error_msg = f"DeepL does not support language '{target_language}'."
            raise ValueError(error_msg)

        try:
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
                self.deepl_translator.translate_document_from_filepath(
                    input_file_path,
                    output_file_path,
                    source_lang=source_language,
                    target_lang=deepl_target_code,
                )
        except deepl.exceptions.DeepLException as deepl_error:
            logger.warning("DeepL document translation failed: %s", deepl_error)
