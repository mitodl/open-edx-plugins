"""Celery tasks for course content translation."""

import json
import logging
from pathlib import Path

from celery import shared_task

from ol_openedx_course_translations.utils import (
    get_srt_output_filename,
    get_translation_provider,
    translate_policy_fields,
    translate_xml_display_name,
    update_video_xml_complete,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, name="translate_file_task")
def translate_file_task(  # noqa: PLR0913
    _self,
    file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    srt_provider_name: str,
    glossary_directory: str | None = None,
):
    """Translate a single file asynchronously."""
    try:
        file_path = Path(file_path_str)

        # Determine which provider to use
        if file_path.suffix == ".srt":
            provider = get_translation_provider(srt_provider_name)
        else:
            provider = get_translation_provider(content_provider_name)

        # Handle SRT files
        if file_path.suffix == ".srt":
            source_lang_pattern = f"-{source_language.lower()}.srt"
            if not file_path.name.lower().endswith(source_lang_pattern):
                return {
                    "status": "skipped",
                    "file": file_path_str,
                    "reason": "Not source language SRT",
                }

            output_filename = get_srt_output_filename(
                file_path.name, source_language, target_language
            )
            output_file_path = file_path.parent / output_filename

            provider.translate_document(
                file_path, output_file_path, source_language, target_language
            )

            return {
                "status": "success",
                "file": file_path_str,
                "output": str(output_file_path),
            }

        # Handle other files
        file_content = file_path.read_text(encoding="utf-8")

        tag_handling_mode = None
        if file_path.suffix in [".xml", ".html"]:
            tag_handling_mode = file_path.suffix.lstrip(".")

        translated_content = provider.translate_text(
            file_content,
            target_language.lower(),
            tag_handling=tag_handling_mode,
            glossary_file=glossary_directory,
        )

        # Handle XML display_name translation
        if file_path.suffix == ".xml":
            translated_content = translate_xml_display_name(
                translated_content, target_language, provider, glossary_directory
            )

            # Update video XML if needed (use complete version)
            if file_path.parent.name == "video":
                translated_content = update_video_xml_complete(
                    translated_content, target_language
                )

        file_path.write_text(translated_content, encoding="utf-8")
    except Exception as e:
        logger.exception("Failed to translate file %s", file_path_str)
        return {"status": "error", "file": file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": file_path_str}


@shared_task(bind=True, name="translate_grading_policy_task")
def translate_grading_policy_task(
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    glossary_directory: str | None = None,
):
    """Translate grading_policy.json file."""
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name)

        grading_policy_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        policy_updated = False

        for grader_item in grading_policy_data.get("GRADER", []):
            if "short_label" in grader_item:
                translated_label = provider.translate_text(
                    grader_item["short_label"],
                    target_language.lower(),
                    glossary_file=glossary_directory,
                )
                grader_item["short_label"] = translated_label
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
def translate_policy_json_task(
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    glossary_directory: str | None = None,
):
    """Translate policy.json file."""
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name)

        policy_json_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        policy_updated = False

        for course_policy_obj in policy_json_data.values():
            if not isinstance(course_policy_obj, dict):
                continue

            # Translate various fields using utility function
            if translate_policy_fields(
                course_policy_obj, target_language, provider, glossary_directory
            ):
                policy_updated = True

        if policy_updated:
            policy_file_path.write_text(
                json.dumps(policy_json_data, ensure_ascii=False, indent=4),
                encoding="utf-8",
            )
    except Exception as e:
        logger.exception("Failed to translate policy.json %s", policy_file_path_str)
        return {"status": "error", "file": policy_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": policy_file_path_str}
