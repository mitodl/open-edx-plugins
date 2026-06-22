"""Celery tasks for course content translation."""

import json
import logging
import re
from pathlib import Path

from celery import shared_task
from defusedxml import ElementTree
from django.conf import settings

from ol_openedx_course_translations.providers.llm_providers import (
    TRANSLATION_MARKER_END,
    TRANSLATION_MARKER_START,
)
from ol_openedx_course_translations.utils.constants import XML_FORMAT_ATTR
from ol_openedx_course_translations.utils.course_translations import (
    apply_format_attribute_mapping,
    get_srt_output_filename,
    get_translation_provider,
    translate_policy_fields,
    update_video_xml_complete,
)

logger = logging.getLogger(__name__)

TRANSLATE_FILE_TASK_LIMITS = getattr(
    settings,
    "TRANSLATE_FILE_TASK_LIMITS",
    {
        "soft_time_limit": 9 * 60,  # 9 minutes
        "time_limit": 10 * 60,  # 10 minutes
        "max_retries": 1,  # 1 Initial try + 1 retry = 2 attempts
        "retry_countdown": 1 * 60,  # wait 1m before retry
    },
)


def _parse_marker_wrapped_translation(raw_text: str) -> str | None:
    """
    Parse translation text wrapped in specific start/end markers.
    """
    if not raw_text:
        return None

    # Tolerant pattern (handles whitespace/newlines and any provider echo)
    pattern = re.compile(
        re.escape(TRANSLATION_MARKER_START)
        + r"(.*?)"
        + re.escape(TRANSLATION_MARKER_END),
        flags=re.DOTALL,
    )
    match = pattern.search(raw_text)
    if match:
        return match.group(1).strip()

    # Case-insensitive fallback (some providers might alter marker casing)
    pattern_case_insensitive = re.compile(
        re.escape(TRANSLATION_MARKER_START)
        .replace("TRANSLATION", "translation")
        .replace("START", "start")
        + r"(.*?)"
        + re.escape(TRANSLATION_MARKER_END)
        .replace("TRANSLATION", "translation")
        .replace("END", "end"),
        flags=re.DOTALL,
    )
    match_ci = pattern_case_insensitive.search(raw_text)
    if match_ci:
        return match_ci.group(1).strip()

    return None


def _looks_like_markup(value: str) -> bool:
    """
    Heuristic to determine if a string looks like markup (XML/HTML).
    """
    if not value:
        return False
    # Require at least one tag-like token; avoid accepting plain prose
    return bool(re.search(r"</?[\w:-]+(?:\s|>|/)", value))


@shared_task(
    bind=True,
    name="translate_file_task",
    soft_time_limit=TRANSLATE_FILE_TASK_LIMITS["soft_time_limit"],
    time_limit=TRANSLATE_FILE_TASK_LIMITS["time_limit"],
    autoretry_for=(Exception,),
    retry_kwargs={
        "max_retries": TRANSLATE_FILE_TASK_LIMITS["max_retries"],
        "countdown": TRANSLATE_FILE_TASK_LIMITS["retry_countdown"],
    },
    retry_backoff=False,  # keep retries predictable
)
def translate_file_task(  # noqa: PLR0913, PLR0912, C901
    _self,
    file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    srt_provider_name: str,
    srt_model: str | None,
    content_glossary: str | None = None,
    srt_glossary: str | None = None,
    translation_validation_provider_name: str | None = None,
    translation_validation_model: str | None = None,
    grading_type_mapping: dict[str, str] | None = None,
):
    """
    Translate a single file asynchronously.

    Handles translation of various file types including SRT subtitles,
    XML, and HTML files. Uses appropriate translation provider based on file type.

    Args:
        _self: Celery task instance (bound)
        file_path_str: Path to the file to translate
        source_language: Source language code
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        srt_provider_name: Provider name for SRT translation
        srt_model: Model name for SRT provider (optional)
        content_glossary: Path to glossary directory for content (optional)
        srt_glossary: Path to glossary directory for SRT (optional)
        translation_validation_provider_name: Provider name for post-translation
            validation (optional)
        translation_validation_model: Model name for validation provider (optional)
        grading_type_mapping: Mapping of original grading type values to their
            translated equivalents from the grading policy file. When provided,
            the ``format`` attribute of XML files is replaced with the
            consistent grading-policy translation instead of relying on the
            translation provider. (optional)

    Returns:
        Dict with status, file path, and optional error or output information
    """
    try:
        file_path = Path(file_path_str)

        # Handle SRT files
        if file_path.suffix == ".srt":
            provider = get_translation_provider(srt_provider_name, srt_model)

            source_lang_pattern = f"-{source_language}.srt"
            if not file_path.name.endswith(source_lang_pattern):
                return {
                    "status": "skipped",
                    "file": file_path_str,
                    "reason": "Not source language SRT",
                }

            output_filename = get_srt_output_filename(file_path.name, target_language)
            output_file_path = file_path.parent / output_filename

            provider.translate_document(
                file_path,
                output_file_path,
                source_language,
                target_language,
                srt_glossary,
            )

            return {
                "status": "success",
                "file": file_path_str,
                "output": str(output_file_path),
            }

        # Handle other files
        file_content = file_path.read_text(encoding="utf-8")

        # Capture original format attribute before translation so we can
        # override it with the pre-translated grading policy value later.
        original_format_value = None
        if file_path.suffix == ".xml" and grading_type_mapping:
            try:
                xml_root = ElementTree.fromstring(file_content)
                original_format_value = xml_root.attrib.get(XML_FORMAT_ATTR)
            except ElementTree.ParseError:
                pass

        tag_handling_mode = None
        if file_path.suffix in [".xml", ".html"]:
            tag_handling_mode = file_path.suffix.lstrip(".")

        provider = get_translation_provider(content_provider_name, content_model)
        translated_content = provider.translate_text(
            file_content,
            target_language,
            tag_handling=tag_handling_mode,
            glossary_directory=content_glossary,
        )

        # Update video XML if needed (use complete version)
        if file_path.suffix == ".xml" and file_path.parent.name == "video":
            translated_content = update_video_xml_complete(
                translated_content,
                target_language,
            )

        # Post-translation validation/fix for XML/HTML (optional)
        if (
            file_path.suffix in [".xml", ".html"]
            and translation_validation_provider_name
            and translated_content
            and translated_content.strip()
        ):
            validation_provider = get_translation_provider(
                translation_validation_provider_name, translation_validation_model
            )
            validated_content = None
            try:
                validated_response = validation_provider.validate_translation(
                    source_language=source_language,
                    target_language=target_language,
                    source_content=file_content,
                    translated_content=translated_content,
                )
                # validate_translation already parses markers via
                # _parse_text_response, but keep an extra safety parse
                # in case provider returns raw marker-wrapped text.
                validated_content = (
                    _parse_marker_wrapped_translation(validated_response)
                    or validated_response
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "XML/HTML validation via LLM provider %s failed for %s: %s",
                    translation_validation_provider_name,
                    file_path_str,
                    str(e),
                )
                validated_content = None

            if validated_content is None:
                pass
            elif _looks_like_markup(validated_content):
                translated_content = validated_content
            else:
                msg = (
                    "XML/HTML validation provider returned non-markup output for %s; "
                    "keeping original translation. Response snippet: %r"
                )
                logger.warning(
                    msg,
                    file_path_str,
                    (validated_content or "")[:500],
                )

        # Apply the pre-translated grading type mapping to the format attribute
        # to ensure consistency between grading policy and XML content translations.
        if (
            file_path.suffix == ".xml"
            and grading_type_mapping
            and original_format_value
        ):
            translated_content = apply_format_attribute_mapping(
                translated_content,
                original_format_value,
                grading_type_mapping,
            )

        file_path.write_text(translated_content, encoding="utf-8")
    except Exception as e:
        logger.exception("Failed to translate file %s", file_path_str)
        return {"status": "error", "file": file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": file_path_str}


@shared_task(bind=True, name="translate_policy_json_task")
def translate_policy_json_task(
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    content_glossary: str | None = None,
):
    """
    Translate policy.json file.

    Translates various policy fields including display names, discussion topics,
    learning info, tabs, and XML attributes.

    Args:
        _self: Celery task instance (bound)
        policy_file_path_str: Path to the policy.json file
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        content_glossary: Path to glossary directory for content (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        policy_json_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        for course_policy_obj in policy_json_data.values():
            if not isinstance(course_policy_obj, dict):
                continue

            translate_policy_fields(
                course_policy_obj, target_language, provider, content_glossary
            )

        policy_file_path.write_text(
            json.dumps(policy_json_data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
    except Exception as e:
        logger.exception("Failed to translate policy.json %s", policy_file_path_str)
        return {"status": "error", "file": policy_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": policy_file_path_str}


@shared_task(bind=True, name="translate_info_updates_task")
def translate_info_updates_task(  # noqa: PLR0913, C901
    _self,
    updates_file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    content_glossary: str | None = None,
    translation_validation_provider_name: str | None = None,
    translation_validation_model: str | None = None,
):
    """
    Translate info/updates.items.json file.

    Translates the ``content`` field (HTML string) for each update item.

    Args:
        _self: Celery task instance (bound)
        updates_file_path_str: Path to the updates.items.json file
        source_language: Source language code
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        content_glossary: Path to glossary directory for content (optional)
        translation_validation_provider_name: Provider name for post-translation
            validation (optional)
        translation_validation_model: Model name for validation provider (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        updates_file_path = Path(updates_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        updates_data = json.loads(updates_file_path.read_text(encoding="utf-8"))
        if not isinstance(updates_data, list):
            msg = "updates.items.json must contain a list of update items"
            raise TypeError(msg)  # noqa: TRY301

        for update_item in updates_data:
            if not isinstance(update_item, dict):
                continue

            content = update_item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue

            translated_content = provider.translate_text(
                content,
                target_language,
                tag_handling="html",
                glossary_directory=content_glossary,
            )

            if (
                translation_validation_provider_name
                and translated_content
                and translated_content.strip()
            ):
                validation_provider = get_translation_provider(
                    translation_validation_provider_name,
                    translation_validation_model,
                )
                validated_content = None
                try:
                    validated_response = validation_provider.validate_translation(
                        source_language=source_language,
                        target_language=target_language,
                        source_content=content,
                        translated_content=translated_content,
                    )
                    validated_content = (
                        _parse_marker_wrapped_translation(validated_response)
                        or validated_response
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "updates.items.json validation via provider %s failed "
                        "for %s: %s",
                        translation_validation_provider_name,
                        updates_file_path_str,
                        str(e),
                    )

                if validated_content and _looks_like_markup(validated_content):
                    translated_content = validated_content
                elif validated_content is not None:
                    logger.warning(
                        "updates.items.json validation provider returned "
                        "non-markup output for %s; keeping original translation. "
                        "Response snippet: %r",
                        updates_file_path_str,
                        validated_content[:500],
                    )

            update_item["content"] = translated_content

        updates_file_path.write_text(
            json.dumps(updates_data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
    except Exception as e:
        logger.exception(
            "Failed to translate updates.items.json %s", updates_file_path_str
        )
        return {"status": "error", "file": updates_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": updates_file_path_str}
