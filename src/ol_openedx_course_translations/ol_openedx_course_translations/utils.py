"""Utility functions for course translations."""

import json
import logging
import re
import shutil
import tarfile
from pathlib import Path
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from django.conf import settings
from django.core.management.base import CommandError

from ol_openedx_course_translations.constants import (
    PROVIDER_DEEPL,
    PROVIDER_GEMINI,
    PROVIDER_MISTRAL,
    PROVIDER_OPENAI,
    TAR_FILE_SIZE_LIMIT,
)
from ol_openedx_course_translations.providers.deepl_provider import DeepLProvider
from ol_openedx_course_translations.providers.llm_provider import (
    GeminiProvider,
    MistralProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)


def get_translation_provider(  # noqa: C901
    provider_name: str,
    openai_model: str | None = None,
    gemini_model: str | None = None,
    mistral_model: str | None = None,
):
    """
    Get translation provider instance based on provider name.

    Args:
        provider_name: Name of the provider (deepl, openai, gemini, mistral)
        openai_model: OpenAI model name to use
        gemini_model: Gemini model name to use
        mistral_model: Mistral model name to use

    Returns:
        Translation provider instance

    Raises:
        ValueError: If provider name is unknown or API key is missing
    """
    # Handle DeepL separately (uses DEEPL_API_KEY setting)
    if provider_name == PROVIDER_DEEPL:
        deepl_api_key = getattr(settings, "DEEPL_API_KEY", "")
        if not deepl_api_key:
            msg = "DEEPL_API_KEY is required for DeepL provider"
            raise ValueError(msg)

        # Get OpenAI API key for repair functionality
        openai_api_key = getattr(settings, "OPENAI_API_KEY", "")
        return DeepLProvider(deepl_api_key, openai_api_key)

    # Handle LLM providers (use TRANSLATIONS_PROVIDERS dict)
    providers_config = getattr(settings, "TRANSLATIONS_PROVIDERS", {})

    if provider_name not in providers_config:
        msg = f"Unknown provider: {provider_name}"
        raise ValueError(msg)

    provider_config = providers_config[provider_name]
    api_key = provider_config.get("api_key", "")

    if not api_key:
        msg = f"API key is required for {provider_name} provider"
        raise ValueError(msg)

    # Get OpenAI API key for repair functionality
    openai_api_key = providers_config.get("openai", {}).get("api_key", "")

    if provider_name == PROVIDER_OPENAI:
        model = openai_model or provider_config.get("default_model")
        if not model:
            msg = "Model name is required for OpenAI provider"
            raise ValueError(msg)
        return OpenAIProvider(api_key, openai_api_key, model)

    elif provider_name == PROVIDER_GEMINI:
        model = gemini_model or provider_config.get("default_model")
        if not model:
            msg = "Model name is required for Gemini provider"
            raise ValueError(msg)
        return GeminiProvider(api_key, openai_api_key, model)

    elif provider_name == PROVIDER_MISTRAL:
        model = mistral_model or provider_config.get("default_model")
        if not model:
            msg = "Model name is required for Mistral provider"
            raise ValueError(msg)
        return MistralProvider(api_key, openai_api_key, model)

    else:
        msg = f"Unknown provider: {provider_name}"
        raise ValueError(msg)


def translate_xml_display_name(
    xml_content: str,
    target_language: str,
    provider,
    glossary_directory: str | None = None,
) -> str:
    """
    Translate display_name attribute in XML content.

    This function is used primarily with DeepL for separate display_name translation.
    LLM providers handle display_name translation as part of the full XML translation.

    Args:
        xml_content: XML content as string
        target_language: Target language code
        provider: Translation provider instance
        glossary_directory: Optional glossary directory path

    Returns:
        Updated XML content with translated display_name
    """
    try:
        xml_root = ElementTree.fromstring(xml_content)
        display_name = xml_root.attrib.get("display_name")

        if display_name:
            translated_name = provider.translate_text(
                display_name,
                target_language.lower(),
                glossary_file=glossary_directory,
            )
            xml_root.set("display_name", translated_name)
            return ElementTree.tostring(xml_root, encoding="unicode")
    except ElementTree.ParseError as e:
        logger.warning("Failed to parse XML for display_name translation: %s", e)

    return xml_content


def update_video_xml_transcripts(xml_content: str, target_language: str) -> str:
    """
    Update video XML transcripts for target language.

    Args:
        xml_content: XML content as string
        target_language: Target language code

    Returns:
        Updated XML content with target language transcripts
    """
    try:
        xml_root = ElementTree.fromstring(xml_content)
        target_lang_code = target_language.lower()

        # Update transcripts attribute in <video> tag
        if xml_root.tag == "video" and "transcripts" in xml_root.attrib:
            transcripts_json_str = xml_root.attrib["transcripts"].replace("&quot;", '"')
            transcripts_dict = json.loads(transcripts_json_str)

            for key in list(transcripts_dict.keys()):
                value = transcripts_dict[key]
                new_value = re.sub(
                    r"-[a-zA-Z]{2}\.srt$",
                    f"-{target_lang_code}.srt",
                    value,
                )
                transcripts_dict[target_lang_code] = new_value

            xml_root.set(
                "transcripts", json.dumps(transcripts_dict, ensure_ascii=False)
            )

        return ElementTree.tostring(xml_root, encoding="unicode")
    except (ElementTree.ParseError, json.JSONDecodeError) as e:
        logger.warning("Failed to update video XML transcripts: %s", e)
        return xml_content


def update_course_language_attribute(course_dir: Path, target_language: str) -> None:
    """
    Update language attribute in course XML files.

    Args:
        course_dir: Parent course directory path
        target_language: Target language code
    """
    for xml_file in (course_dir / "course").glob("*.xml"):
        try:
            xml_content = xml_file.read_text(encoding="utf-8")
            xml_root = ElementTree.fromstring(xml_content)

            # Check if root tag is 'course' and has language attribute
            if xml_root.tag == "course" and "language" in xml_root.attrib:
                current_language = xml_root.attrib["language"]
                xml_root.set("language", target_language.lower())
                updated_xml_content = ElementTree.tostring(xml_root, encoding="unicode")
                xml_file.write_text(updated_xml_content, encoding="utf-8")
                logger.debug(
                    "Updated language attribute in %s from %s to %s",
                    xml_file,
                    current_language,
                    target_language.lower(),
                )
        except (OSError, ElementTree.ParseError) as e:
            logger.warning("Failed to update language attribute in %s: %s", xml_file, e)


def translate_policy_fields(  # noqa: C901
    course_policy_obj: dict,
    target_language: str,
    provider,
    glossary_directory: str | None = None,
) -> None:
    """
    Translate fields in policy object.

    Args:
        course_policy_obj: Policy object dictionary
        target_language: Target language code
        provider: Translation provider instance
        glossary_directory: Optional glossary directory path
    """
    # Translate string fields
    string_fields = ["advertised_start", "display_name", "display_organization"]
    for field in string_fields:
        if field in course_policy_obj:
            translated = provider.translate_text(
                course_policy_obj[field],
                target_language.lower(),
                glossary_file=glossary_directory,
            )
            course_policy_obj[field] = translated

    # Update language attribute
    course_policy_obj["language"] = target_language.lower()

    # Translate discussion topics
    if "discussion_topics" in course_policy_obj:
        topics = course_policy_obj["discussion_topics"]
        if isinstance(topics, dict):
            translated_topics = {}
            for key, value in topics.items():
                translated_key = provider.translate_text(
                    key, target_language.lower(), glossary_file=glossary_directory
                )
                translated_topics[translated_key] = value
            course_policy_obj["discussion_topics"] = translated_topics

    # Translate learning info
    if "learning_info" in course_policy_obj and isinstance(
        course_policy_obj["learning_info"], list
    ):
        translated_info = [
            provider.translate_text(
                item, target_language.lower(), glossary_file=glossary_directory
            )
            for item in course_policy_obj["learning_info"]
        ]
        course_policy_obj["learning_info"] = translated_info

    # Translate tabs
    if "tabs" in course_policy_obj and isinstance(course_policy_obj["tabs"], list):
        for tab in course_policy_obj["tabs"]:
            if isinstance(tab, dict) and "name" in tab:
                tab["name"] = provider.translate_text(
                    tab["name"],
                    target_language.lower(),
                    glossary_file=glossary_directory,
                )

    # Translate XML attributes
    if "xml_attributes" in course_policy_obj and isinstance(
        course_policy_obj["xml_attributes"], dict
    ):
        xml_attributes_dict = course_policy_obj["xml_attributes"]
        translatable_xml_fields = ["diplay_name", "info_sidebar_name"]
        for xml_field_name in translatable_xml_fields:
            if xml_field_name in xml_attributes_dict:
                translated_value = provider.translate_text(
                    xml_attributes_dict[xml_field_name],
                    target_language.lower(),
                    glossary_file=glossary_directory,
                )
                xml_attributes_dict[xml_field_name] = translated_value


def get_srt_output_filename(input_filename: str, target_language: str) -> str:
    """
    Generate output filename for translated SRT file.

    Args:
        input_filename: Original SRT filename
        target_language: Target language code

    Returns:
        Output filename with target language code
    """
    if "-" in input_filename and input_filename.endswith(".srt"):
        filename_parts = input_filename.rsplit("-", 1)
        return f"{filename_parts[0]}-{target_language.lower()}.srt"
    return input_filename


def get_supported_archive_extension(filename: str) -> str | None:
    """
    Return the supported archive extension if filename ends with one, else None.

    Args:
        filename: Name of the archive file

    Returns:
        Archive extension if supported, None otherwise
    """
    for ext in settings.COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS:
        if filename.endswith(ext):
            return ext
    return None


def validate_tar_file(tar_file: tarfile.TarFile) -> None:
    """
    Validate tar file contents for security.

    Args:
        tar_file: Open tarfile object

    Raises:
        CommandError: If tar file contains unsafe members or excessively large files
    """
    for tar_member in tar_file.getmembers():
        # Check for directory traversal attacks
        if tar_member.name.startswith("/") or ".." in tar_member.name:
            error_msg = f"Unsafe tar member: {tar_member.name}"
            raise CommandError(error_msg)
        # Check for excessively large files (512MB limit)
        if tar_member.size > TAR_FILE_SIZE_LIMIT:
            error_msg = f"File too large: {tar_member.name}"
            raise CommandError(error_msg)


def extract_course_archive(course_archive_path: Path) -> Path:
    """
    Extract course archive to working directory.

    Args:
        course_archive_path: Path to the course archive file

    Returns:
        Path to extracted course directory

    Raises:
        CommandError: If extraction fails
    """
    # Use the parent directory of the source file as the base extraction directory
    extraction_base_dir = course_archive_path.parent

    # Get base name without extension
    archive_extension = get_supported_archive_extension(course_archive_path.name)
    archive_base_name = (
        course_archive_path.name[: -len(archive_extension)]
        if archive_extension
        else course_archive_path.name
    )

    extracted_course_dir = extraction_base_dir / archive_base_name

    if not extracted_course_dir.exists():
        try:
            with tarfile.open(course_archive_path, "r:*") as tar_file:
                # Validate tar file before extraction
                validate_tar_file(tar_file)
                tar_file.extractall(path=extracted_course_dir, filter="data")
        except (tarfile.TarError, OSError) as e:
            error_msg = f"Failed to extract archive: {e}"
            raise CommandError(error_msg) from e

    logger.info("Extracted course to: %s", extracted_course_dir)
    return extracted_course_dir


def create_translated_copy(source_course_dir: Path, target_language: str) -> Path:
    """
    Create a copy of the course for translation.

    Args:
        source_course_dir: Path to source course directory
        target_language: Target language code

    Returns:
        Path to translated course directory

    Raises:
        CommandError: If translation directory already exists
    """
    source_base_name = source_course_dir.name
    translated_dir_name = f"{target_language}_{source_base_name}"
    translated_course_dir = source_course_dir.parent / translated_dir_name

    if translated_course_dir.exists():
        error_msg = f"Translation directory already exists: {translated_course_dir}"
        raise CommandError(error_msg)

    shutil.copytree(source_course_dir, translated_course_dir)
    logger.info("Created translation copy: %s", translated_course_dir)
    return translated_course_dir


def create_translated_archive(
    translated_course_dir: Path,
    target_language: str,
    original_archive_name: str,
) -> Path:
    """
    Create tar.gz archive of translated course.

    Args:
        translated_course_dir: Path to translated course directory
        target_language: Target language code
        original_archive_name: Original archive filename

    Returns:
        Path to created archive
    """
    # Remove all archive extensions from the original name
    archive_extension = get_supported_archive_extension(original_archive_name)
    clean_archive_name = (
        original_archive_name[: -len(archive_extension)]
        if archive_extension
        else original_archive_name
    )

    translated_archive_name = f"{target_language}_{clean_archive_name}.tar.gz"
    translated_archive_path = translated_course_dir.parent / translated_archive_name

    # Remove existing archive
    if translated_archive_path.exists():
        translated_archive_path.unlink()

    # Create tar.gz archive containing only the 'course' directory
    course_directory_path = translated_course_dir / "course"
    with tarfile.open(translated_archive_path, "w:gz") as tar_archive:
        tar_archive.add(course_directory_path, arcname="course")

    # Delete extracted directory after archiving
    if translated_course_dir.exists():
        shutil.rmtree(translated_course_dir)

    logger.info("Created tar.gz archive: %s", translated_archive_path)
    return translated_archive_path


def update_video_xml_complete(xml_content: str, target_language: str) -> str:  # noqa: C901
    """
    Update video XML transcripts and transcript tags for the target language.
    This is a more complete version that handles nested transcript elements.

    Args:
        xml_content: XML content as string
        target_language: Target language code

    Returns:
        Updated XML content with all video transcript references
    """
    try:
        xml_root = ElementTree.fromstring(xml_content)
        target_lang_code = target_language.lower()

        # Update transcripts attribute in <video>
        if xml_root.tag == "video" and "transcripts" in xml_root.attrib:
            transcripts_json_str = xml_root.attrib["transcripts"].replace("&quot;", '"')
            transcripts_dict = json.loads(transcripts_json_str)
            for transcript_key in list(transcripts_dict.keys()):
                transcript_value = transcripts_dict[transcript_key]
                new_transcript_key = target_lang_code
                new_transcript_value = re.sub(
                    r"-[a-zA-Z]{2}\.srt$",
                    f"-{new_transcript_key}.srt",
                    transcript_value,
                )
                transcripts_dict[new_transcript_key] = new_transcript_value
            updated_transcripts_json = json.dumps(transcripts_dict, ensure_ascii=False)
            xml_root.set("transcripts", updated_transcripts_json)

        # Add a new <transcript> tag inside <transcripts> for the target language
        for video_asset_element in xml_root.findall("video_asset"):
            for transcripts_element in video_asset_element.findall("transcripts"):
                existing_transcript_element = transcripts_element.find("transcript")
                new_transcript_element = Element("transcript")
                if existing_transcript_element is not None:
                    new_transcript_element.attrib = (
                        existing_transcript_element.attrib.copy()
                    )
                new_transcript_element.set("language_code", target_lang_code)
                # Avoid duplicates
                if not any(
                    transcript_elem.attrib == new_transcript_element.attrib
                    for transcript_elem in transcripts_element.findall("transcript")
                ):
                    transcripts_element.append(new_transcript_element)

        # Add a new <transcript> tag for the target language
        for transcript_element in xml_root.findall("transcript"):
            transcript_src = transcript_element.get("src")
            if transcript_src:
                new_transcript_src = re.sub(
                    r"-[a-zA-Z]{2}\.srt$",
                    f"-{target_lang_code}.srt",
                    transcript_src,
                )
                new_transcript_element = Element("transcript")
                new_transcript_element.set("language", target_lang_code)
                new_transcript_element.set("src", new_transcript_src)
                # Avoid duplicates
                if not any(
                    existing_transcript.get("language") == target_lang_code
                    and existing_transcript.get("src") == new_transcript_src
                    for existing_transcript in xml_root.findall("transcript")
                ):
                    xml_root.append(new_transcript_element)

        return ElementTree.tostring(xml_root, encoding="unicode")
    except (ElementTree.ParseError, json.JSONDecodeError, KeyError) as e:
        logger.warning("Failed to update video XML completely: %s", e)
        return xml_content


def validate_course_inputs(
    course_archive_path: Path,
) -> None:
    """
    Validate command inputs for course translation.

    Args:
        course_archive_path: Path to course archive file

    Raises:
        CommandError: If validation fails
    """
    if not course_archive_path.exists():
        error_msg = f"Course archive not found: {course_archive_path}"
        raise CommandError(error_msg)

    if get_supported_archive_extension(course_archive_path.name) is None:
        supported_extensions = ", ".join(
            settings.COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS
        )
        error_msg = f"Course archive must be a tar file: {supported_extensions}"
        raise CommandError(error_msg)


def get_translatable_file_paths(
    directory_path: Path,
    *,
    recursive: bool = False,
) -> list[Path]:
    """
    Get list of translatable file paths from a directory.

    Args:
        directory_path: Path to directory to scan
        recursive: Whether to search recursively

    Returns:
        List of translatable file paths
    """
    if recursive:
        translatable_file_paths: list[Path] = []
        for file_extension in settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS:
            translatable_file_paths.extend(directory_path.rglob(f"*{file_extension}"))
    else:
        translatable_file_paths = [
            file_path
            for file_path in directory_path.iterdir()
            if file_path.is_file()
            and any(
                file_path.name.endswith(extension)
                for extension in settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS
            )
        ]

    return translatable_file_paths
