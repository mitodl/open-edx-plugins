"""Celery tasks for course content translation."""

import json
import logging
from pathlib import Path

from celery import shared_task
from django.conf import settings

from ol_openedx_course_translations.providers.deepl_provider import DeepLProvider
from ol_openedx_course_translations.utils.course_translations import (
    get_srt_output_filename,
    get_translation_provider,
    translate_policy_fields,
    translate_xml_attributes,
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
def translate_file_task(  # noqa: PLR0913
    _self,
    file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    srt_provider_name: str,
    srt_model: str | None,
    validation_provider_name: str | None = None,
    validation_model: str | None = None,
    content_glossary: str | None = None,
    srt_glossary: str | None = None,
):
    """
    Translate a single file asynchronously with optional validation.

    Handles translation of various file types including SRT subtitles,
    XML, and HTML files. Uses appropriate translation provider based on file type.
    Optionally validates and corrects content translations.

    Args:
        _self: Celery task instance (bound)
        file_path_str: Path to the file to translate
        source_language: Source language code
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        srt_provider_name: Provider name for SRT translation
        srt_model: Model name for SRT provider (optional)
        validation_provider_name: Provider name for validation (optional)
        validation_model: Model name for validation provider (optional)
        content_glossary: Path to glossary directory for content (optional)
        srt_glossary: Path to glossary directory for SRT (optional)

    Returns:
        Dict with status, file path, and optional error or output information
    """
    try:
        file_path = Path(file_path_str)

        # Handle SRT files
        if file_path.suffix == ".srt":
            provider = get_translation_provider(srt_provider_name, srt_model)

            source_lang_pattern = f"-{source_language.lower()}.srt"
            if not file_path.name.lower().endswith(source_lang_pattern):
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

        # Handle other files (XML, HTML, text)
        file_content = file_path.read_text(encoding="utf-8")

        tag_handling_mode = None
        if file_path.suffix in [".xml", ".html"]:
            tag_handling_mode = file_path.suffix.lstrip(".")

        provider = get_translation_provider(content_provider_name, content_model)
        translated_content = provider.translate_text(
            file_content,
            target_language.lower(),
            tag_handling=tag_handling_mode,
            glossary_directory=content_glossary,
        )

        # Validate and correct translation if validation provider is specified
        validation_enabled = getattr(settings, "TRANSLATION_VALIDATION_ENABLED", True)
        if validation_provider_name and validation_enabled:
            translated_content = _validate_and_correct_translation(
                original_text=file_content,
                translated_text=translated_content,
                target_language=target_language,
                content_provider=provider,
                validation_provider_name=validation_provider_name,
                validation_model=validation_model,
                glossary_directory=content_glossary,
                file_path=file_path_str,
            )

        # Handle XML display_name translation only for DeepL provider
        # LLM providers translate display_name as part of the XML translation
        if file_path.suffix == ".xml" and isinstance(provider, DeepLProvider):
            translated_content = translate_xml_attributes(
                translated_content, target_language, provider, content_glossary
            )

        # Update video XML if needed (use complete version)
        if file_path.suffix == ".xml" and file_path.parent.name == "video":
            translated_content = update_video_xml_complete(
                translated_content, target_language
            )

        logger.info("\n\n%s\n\n", translated_content)
        file_path.write_text(translated_content, encoding="utf-8")
    except Exception as e:
        logger.exception("Failed to translate file %s", file_path_str)
        return {"status": "error", "file": file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": file_path_str}


def _validate_and_correct_translation(  # noqa: PLR0913
    original_text: str,
    translated_text: str,
    target_language: str,
    content_provider,
    validation_provider_name: str,
    validation_model: str | None,
    glossary_directory: str | None,
    file_path: str,
) -> str:
    """
    Validate and optionally correct a translation.

    Args:
        original_text: Original text
        translated_text: Translated text
        target_language: Target language code
        content_provider: Provider used for initial translation
        validation_provider_name: Provider name for validation
        validation_model: Model for validation provider
        glossary_directory: Glossary directory path
        file_path: File path for logging

    Returns:
        Final translation (original, corrected, or fallback)
    """
    try:
        # Get validation provider
        validation_provider = get_translation_provider(
            validation_provider_name, validation_model
        )

        # Validate initial translation
        logger.info("Validating translation for: %s", file_path)
        validation_result = content_provider.validate_translation(
            original_text,
            translated_text,
            target_language.lower(),
            validation_provider,
        )

        initial_score = validation_result.get("score", 10)
        issues = validation_result.get("issues", [])

        logger.info("Initial validation score: %d/10 for %s", initial_score, file_path)

        # Check if correction is needed
        min_score = getattr(settings, "TRANSLATION_VALIDATION_MIN_SCORE", 7)
        if initial_score >= min_score or not issues:
            logger.info("Translation quality acceptable for: %s", file_path)
            return translated_text

        logger.info(
            "Translation needs correction (%d issues) for: %s", len(issues), file_path
        )
        for i, issue in enumerate(issues[:5], 1):
            logger.info("  Issue %d: %s", i, issue)
        if len(issues) > 5:  # noqa: PLR2004
            logger.info("  ... and %d more issues", len(issues) - 5)

        # Attempt correction using content provider
        corrected_text = content_provider.correct_translation(
            original_text,
            translated_text,
            issues,
            target_language.lower(),
            glossary_directory,
        )

        # Re-validate corrected translation
        logger.info("Re-validating corrected translation for: %s", file_path)
        corrected_validation = content_provider.validate_translation(
            original_text,
            corrected_text,
            target_language.lower(),
            validation_provider,
        )

        corrected_score = corrected_validation.get("score", 0)
        logger.info(
            "Corrected validation score: %d/10 for %s", corrected_score, file_path
        )

        # Keep corrected version if score improved or stayed the same
        if corrected_score >= initial_score:
            logger.info(
                "Using corrected translation (score: %d -> %d) for: %s",
                initial_score,
                corrected_score,
                file_path,
            )
            return corrected_text
        else:
            logger.warning(
                "Correction degraded quality (score: %d -> %d), keeping original for: %s",
                initial_score,
                corrected_score,
                file_path,
            )
            return translated_text

    except Exception as e:  # noqa: BLE001
        logger.warning(
            "Validation/correction failed for %s: %s. Using initial translation.",
            file_path,
            e,
        )
        return translated_text


@shared_task(bind=True, name="translate_grading_policy_task")
def translate_grading_policy_task(  # noqa: PLR0913
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    validation_provider_name: str | None = None,
    validation_model: str | None = None,
    content_glossary: str | None = None,
):
    """
    Translate grading_policy.json file with optional validation.

    Translates the short_label fields within the GRADER section of grading policy files.

    Args:
        _self: Celery task instance (bound)
        policy_file_path_str: Path to the grading_policy.json file
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        validation_provider_name: Provider name for validation (optional)
        validation_model: Model name for validation provider (optional)
        content_glossary: Path to glossary directory for content (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        grading_policy_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        policy_updated = False

        keys_to_translate = ["short_label", "type"]
        for grader_item in grading_policy_data.get("GRADER", []):
            for key in keys_to_translate:
                if key in grader_item:
                    original_value = grader_item[key]
                    translated_label = provider.translate_text(
                        original_value,
                        target_language.lower(),
                        glossary_directory=content_glossary,
                    )

                    # Validate and correct if validation provider specified
                    validation_enabled = getattr(
                        settings, "TRANSLATION_VALIDATION_ENABLED", True
                    )
                    if validation_provider_name and validation_enabled:
                        translated_label = _validate_and_correct_translation(
                            original_text=original_value,
                            translated_text=translated_label,
                            target_language=target_language,
                            content_provider=provider,
                            validation_provider_name=validation_provider_name,
                            validation_model=validation_model,
                            glossary_directory=content_glossary,
                            file_path=f"{policy_file_path_str}:{key}",
                        )

                    grader_item[key] = translated_label
                    policy_updated = True

        if policy_updated:
            policy_file_path.write_text(
                json.dumps(grading_policy_data, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
    except Exception as e:
        logger.exception("Failed to translate grading policy %s", policy_file_path_str)
        return {"status": "error", "file": policy_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": policy_file_path_str}


@shared_task(bind=True, name="translate_policy_json_task")
def translate_policy_json_task(  # noqa: PLR0913
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    validation_provider_name: str | None = None,
    validation_model: str | None = None,
    content_glossary: str | None = None,
):
    """
    Translate policy.json file with optional validation.

    Translates various policy fields including display names, discussion topics,
    learning info, tabs, and XML attributes.

    Args:
        _self: Celery task instance (bound)
        policy_file_path_str: Path to the policy.json file
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        validation_provider_name: Provider name for validation (optional)
        validation_model: Model name for validation provider (optional)
        content_glossary: Path to glossary directory for content (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        # Get validation provider if specified
        validation_provider = None
        validation_enabled = getattr(settings, "TRANSLATION_VALIDATION_ENABLED", True)
        if validation_provider_name and validation_enabled:
            validation_provider = get_translation_provider(
                validation_provider_name, validation_model
            )

        policy_json_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        for course_policy_obj in policy_json_data.values():
            if not isinstance(course_policy_obj, dict):
                continue

            translate_policy_fields(
                course_policy_obj,
                target_language,
                provider,
                content_glossary,
                validation_provider=validation_provider,
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
