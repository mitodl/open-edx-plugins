"""Utility functions for course translations.

This module includes DOM-aware helpers for translating HTML/XML safely by:
- Extracting only text nodes and allowlisted attribute VALUES as independent units
- Sending only those units to translation providers (never raw markup blobs)
- Reinserting translations without changing markup structure, tag names,
or attribute names
"""

import ast
import json
import logging
import re
import shutil
import tarfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from xml.etree.ElementTree import Element

import srt
from defusedxml import ElementTree
from django.conf import settings
from django.core.management.base import CommandError
from lxml import etree
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_course_translations.providers.deepl_provider import DeepLProvider
from ol_openedx_course_translations.providers.llm_providers import (
    GeminiProvider,
    MistralProvider,
    OpenAIProvider,
)
from ol_openedx_course_translations.utils.constants import (
    NEVER_TRANSLATE_ATTRS,
    PROVIDER_DEEPL,
    PROVIDER_GEMINI,
    PROVIDER_MISTRAL,
    PROVIDER_OPENAI,
    TRANSLATABLE_ATTRS_BASE,
    TRANSLATABLE_ATTRS_OPTIONINPUT_ONLY,
)

logger = logging.getLogger(__name__)

# Archive and file size limits
TAR_FILE_SIZE_LIMIT = 512 * 1024 * 1024  # 512MB


def _get_deepl_api_key() -> str:
    """
    Get DeepL API key from settings.

    Returns:
        DeepL API key

    Raises:
        ValueError: If DeepL API key is not configured
    """
    providers_config = getattr(settings, "TRANSLATIONS_PROVIDERS", {})

    if PROVIDER_DEEPL in providers_config:
        deepl_config = providers_config[PROVIDER_DEEPL]
        if isinstance(deepl_config, dict):
            api_key = deepl_config.get("api_key", "")
            if api_key:
                return api_key

    msg = (
        "DeepL API key is required. Configure it in "
        "TRANSLATIONS_PROVIDERS['deepl']['api_key']"
    )
    raise ValueError(msg)


def get_translation_provider(
    provider_name: str,
    model_name: str | None = None,
):
    """
    Get translation provider instance based on provider name.

    Note: This function assumes validation has already been done via
    _parse_and_validate_provider_spec() in the management command.

    Args:
        provider_name: Name of the provider (deepl, openai, gemini, mistral)
        model_name: Model name to use

    Returns:
        Translation provider instance

    Raises:
        ValueError: If provider configuration is invalid
    """
    # Handle DeepL
    if provider_name == PROVIDER_DEEPL:
        deepl_api_key = _get_deepl_api_key()
        return DeepLProvider(deepl_api_key)

    # Handle LLM providers
    providers_config = getattr(settings, "TRANSLATIONS_PROVIDERS", {})
    provider_config = providers_config[provider_name]
    api_key = provider_config["api_key"]

    if provider_name == PROVIDER_OPENAI:
        return OpenAIProvider(api_key, model_name)
    elif provider_name == PROVIDER_GEMINI:
        return GeminiProvider(api_key, model_name)
    elif provider_name == PROVIDER_MISTRAL:
        return MistralProvider(api_key, model_name)

    msg = f"Unknown provider: {provider_name}"
    raise ValueError(msg)


def translate_xml_attributes(
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
    attribute_names = ["display_name", "format"]
    try:
        xml_root = ElementTree.fromstring(xml_content)
        is_xml_updated = False
        for attribute_name in attribute_names:
            attribute_value = xml_root.attrib.get(attribute_name)
            if attribute_value:
                translated_value = provider.translate_text(
                    attribute_value,
                    target_language,
                    glossary_directory=glossary_directory,
                )
                xml_root.set(attribute_name, translated_value)
                is_xml_updated = True
        if is_xml_updated:
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
        # Update transcripts attribute in <video> tag
        if xml_root.tag == "video" and "transcripts" in xml_root.attrib:
            transcripts_json_str = xml_root.attrib["transcripts"].replace("&quot;", '"')
            transcripts_dict = json.loads(transcripts_json_str)

            for key in list(transcripts_dict.keys()):
                value = transcripts_dict[key]
                new_value = re.sub(
                    r"-[a-zA-Z]{2}\.srt$",
                    f"-{target_language}.srt",
                    value,
                )
                transcripts_dict[target_language] = new_value

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
                xml_root.set("language", target_language)
                updated_xml_content = ElementTree.tostring(xml_root, encoding="unicode")
                xml_file.write_text(updated_xml_content, encoding="utf-8")
                logger.debug(
                    "Updated language attribute in %s from %s to %s",
                    xml_file,
                    current_language,
                    target_language,
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
                target_language,
                glossary_directory=glossary_directory,
            )
            course_policy_obj[field] = translated

    # Update language attribute
    course_policy_obj["language"] = target_language

    # Translate discussion topics
    if "discussion_topics" in course_policy_obj:
        topics = course_policy_obj["discussion_topics"]
        if isinstance(topics, dict):
            translated_topics = {}
            for key, value in topics.items():
                translated_key = provider.translate_text(
                    key, target_language, glossary_directory=glossary_directory
                )
                translated_topics[translated_key] = value
            course_policy_obj["discussion_topics"] = translated_topics

    # Translate learning info
    if "learning_info" in course_policy_obj and isinstance(
        course_policy_obj["learning_info"], list
    ):
        translated_info = [
            provider.translate_text(
                item, target_language, glossary_directory=glossary_directory
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
                    target_language,
                    glossary_directory=glossary_directory,
                )

    # Translate XML attributes
    if "xml_attributes" in course_policy_obj and isinstance(
        course_policy_obj["xml_attributes"], dict
    ):
        xml_attributes_dict = course_policy_obj["xml_attributes"]
        translatable_xml_fields = ["display_name", "info_sidebar_name"]
        for xml_field_name in translatable_xml_fields:
            if xml_field_name in xml_attributes_dict:
                translated_value = provider.translate_text(
                    xml_attributes_dict[xml_field_name],
                    target_language,
                    glossary_directory=glossary_directory,
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
    target_language = LanguageCode(target_language).to_bcp47()
    if "-" in input_filename and input_filename.endswith(".srt"):
        filename_parts = input_filename.rsplit("-", 1)
        return f"{filename_parts[0]}-{target_language}.srt"
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


def extract_course_archive(course_archive_path: Path, extract_to_dir: Path) -> Path:
    """
    Extract course archive to the specified directory.

    Args:
        course_archive_path: Path to the course archive file
        extract_to_dir: Directory to extract the course archive to

    Returns:
        Path to extracted course directory

    Raises:
        CommandError: If extraction fails
    """
    extraction_base_dir = extract_to_dir

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
    output_dir: Path,
) -> Path:
    """
    Create tar.gz archive of translated course.

    Args:
        translated_course_dir: Path to translated course directory
        target_language: Target language code
        original_archive_name: Original archive filename
        output_dir: Path to the output directory

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

    generated_at = datetime.now(UTC).strftime("%Y%m%d_%H%MZ")
    translated_archive_name = (
        f"{target_language}_{clean_archive_name}_{generated_at}.tar.gz"
    )
    translated_archive_path = output_dir / translated_archive_name

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
        target_language = LanguageCode(target_language).to_bcp47()
        # Update transcripts attribute in <video>
        if xml_root.tag == "video" and "transcripts" in xml_root.attrib:
            transcripts_json_str = xml_root.attrib["transcripts"].replace("&quot;", '"')
            transcripts_dict = json.loads(transcripts_json_str)
            for transcript_key in list(transcripts_dict.keys()):
                transcript_value = transcripts_dict[transcript_key]
                new_transcript_key = target_language
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
                new_transcript_element.set("language_code", target_language)
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
                    f"-{target_language}.srt",
                    transcript_src,
                )
                new_transcript_element = Element("transcript")
                new_transcript_element.set("language", target_language)
                new_transcript_element.set("src", new_transcript_src)
                # Avoid duplicates
                if not any(
                    existing_transcript.get("language") == target_language
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


def generate_course_key_from_xml(course_dir_path: Path) -> str:
    """
    Generate the course id of the source course
    """
    try:
        about_file_path = course_dir_path / "course" / "course.xml"
        xml_content = about_file_path.read_text(encoding="utf-8")
        xml_root = ElementTree.fromstring(xml_content)

        org = xml_root.get("org", "")
        course = xml_root.get("course", "")
        url_name = xml_root.get("url_name", "")

        if not all([org, course, url_name]):
            error_msg = (
                "Missing required attributes in course.xml: org, course, url_name"
            )
            raise CommandError(error_msg)
    except (OSError, ElementTree.ParseError) as e:
        error_msg = f"Failed to read course id from about.xml: {e}"
        raise CommandError(error_msg) from e
    else:
        # URL name is the run ID of the course
        return CourseLocator(org=org, course=course, run=url_name)


@dataclass(frozen=True)
class _TranslationUnitRef:
    """
    Reference to where a translation unit lives in the DOM.

    kind:
      - "text": element.text
      - "tail": element.tail
      - "attr": element.attrib[attr_name]
      - "dict_value": Value at json_path within a script tag (Python dict or JSON)
      - "js_dict_value": Value at json_path within a JS variable in a script tag
      - "js_dict_key": Key at json_path within a JS variable in a script tag
    """

    kind: str
    xpath: str
    attr_name: str | None = None
    json_path: tuple[str | int, ...] | None = None
    js_var_name: str | None = None  # For JS variable assignments


class HtmlXmlTranslationHelper:
    """
    Extract/reinsert small translation units from HTML/XML without altering structure.

    Guarantees (best-effort; parser-dependent):
    - Never changes element/tag names or markup structure.
    - Never changes attribute names; only allowlisted attribute VALUES may be replaced.
    - Preserves whitespace/indentation by keeping leading/trailing whitespace untouched
      and translating only the "core" (stripped) text/attribute value.
    - Applies Open edX-specific rules:
      * Translate `options` and `correct` attribute VALUES ONLY on <optioninput>
      * Never translate `correct` elsewhere
      * Never adds `display_name` (only translates it if present)
    - Translates dictionary content within <script> tags (Python dict or JSON syntax)

    Limitations:
    - HTML parsing with lxml may normalize malformed HTML; prefer XML/XHTML
    where possible.
    - For HTML fragments, serialization attempts to return the <body> inner HTML.
    """

    # Tags whose text content should not be translated (non-user-visible)
    # Note: script tags are handled separately for embedded dictionary content
    _SKIP_TEXT_TAGS = {"script", "style"}

    # Script types that contain pure data (no executable code)
    _DATA_SCRIPT_TYPES = {"application/json", "text/json", "text/python"}

    # Regex patterns to extract object literals from JavaScript variable assignments
    # Matches: const/let/var NAME = { ... }  or  const/let/var NAME = [ ... ]
    _JS_VAR_PATTERN = re.compile(
        r"(?:const|let|var)\s+\w+\s*=\s*(\{[\s\S]*\}|\[[\s\S]*\])\s*;?",
        re.MULTILINE,
    )

    def __init__(self, *, is_xml: bool):
        self.is_xml = is_xml

    def parse(self, raw: str) -> etree._Element:
        if self.is_xml:
            parser = etree.XMLParser(
                resolve_entities=False,
                no_network=True,
                recover=False,
                remove_blank_text=False,
            )
            return etree.fromstring(raw.encode("utf-8"), parser=parser)
        # HTML: keep input formatting as much as possible; do not pretty-print later
        parser = etree.HTMLParser(
            no_network=True,
            remove_blank_text=False,
        )
        return etree.fromstring(raw.encode("utf-8"), parser=parser)

    @staticmethod
    def _split_preserve_outer_ws(value: str) -> tuple[str, str, str]:
        """
        Split a string into (leading_ws, core, trailing_ws) such that:
        value == leading_ws + core + trailing_ws and core has no leading/trailing ws.

        This allows translating only `core` and re-wrapping it to preserve formatting.
        """
        if value is None:
            return "", "", ""
        m = re.match(r"^(\s*)(.*?)(\s*)$", value, flags=re.DOTALL)
        if not m:
            return "", value, ""
        return m.group(1), m.group(2), m.group(3)

    def _iter_elements(self, root: etree._Element) -> Iterable[etree._Element]:
        for el in root.iter():
            # Skip comments / processing instructions
            if not isinstance(el.tag, str):
                continue
            yield el

    def _is_translatable_attr(self, el: etree._Element, attr_name: str) -> bool:
        # Never translate data-* or most aria-* (except aria-label)
        if attr_name.startswith("data-"):
            return False
        if attr_name.startswith("aria-") and attr_name != "aria-label":
            return False

        if attr_name in NEVER_TRANSLATE_ATTRS:
            return False

        if attr_name in TRANSLATABLE_ATTRS_BASE:
            # Open edX: do not add display_name; extraction only happens if exists
            return True

        # Open edX rule: options/correct only inside <optioninput>
        if attr_name in TRANSLATABLE_ATTRS_OPTIONINPUT_ONLY:
            return (el.tag or "").lower() == "optioninput"

        # Do NOT attempt to translate other attributes (incl. value) by default
        return False

    def _is_data_script(self, el: etree._Element) -> bool:
        """Check if element is a script tag containing pure data (JSON/Python dict)."""
        if (el.tag or "").lower() != "script":
            return False
        script_type = el.attrib.get("type", "").lower()
        return script_type in self._DATA_SCRIPT_TYPES

    def _is_js_script_with_dict(self, el: etree._Element) -> bool:
        """Check if element is a JS script tag that may contain object literals."""
        if (el.tag or "").lower() != "script":
            return False
        script_type = el.attrib.get("type", "").lower()
        # Default type (empty or text/javascript) may have JS object literals
        return script_type in ("", "text/javascript", "module")

    @staticmethod
    def _parse_python_dict(text: str) -> dict | list | None:
        """
        Safely parse a Python dictionary/list literal from text.

        Uses ast.literal_eval which only evaluates literals (strings, numbers,
        tuples, lists, dicts, booleans, None) - no arbitrary code execution.

        Args:
            text: String containing Python dict/list literal

        Returns:
            Parsed dict/list, or None if parsing fails
        """
        try:
            result = ast.literal_eval(text.strip())
            if isinstance(result, (dict, list)):
                return result
        except (ValueError, SyntaxError, TypeError):
            pass
        return None

    @staticmethod
    def _convert_js_to_python_literal(js_text: str) -> str:
        """
        Convert JavaScript object/array literal syntax to Python dict/list syntax.

        Handles common differences:
        - true/false/null -> True/False/None
        - Trailing commas (allowed in both)
        - Single-line comments // (removed)

        Args:
            js_text: JavaScript object or array literal

        Returns:
            Python-compatible literal string
        """
        # Remove single-line comments
        text = re.sub(r"//.*$", "", js_text, flags=re.MULTILINE)

        # Replace JavaScript literals with Python equivalents
        # Use word boundaries to avoid replacing inside strings
        text = re.sub(r"\btrue\b", "True", text)
        text = re.sub(r"\bfalse\b", "False", text)
        text = re.sub(r"\bnull\b", "None", text)
        return re.sub(r"\bundefined\b", "None", text)

    def _extract_js_object_literals(self, script_text: str) -> list[tuple[str, str]]:
        """
        Extract object/array literals from JavaScript variable assignments.

        Args:
            script_text: JavaScript code containing variable assignments

        Returns:
            List of (variable_name, object_literal) tuples
        """
        results = []

        # Pattern to match: const/let/var NAME = { ... } or [ ... ]
        # We need to handle nested braces/brackets properly
        var_pattern = re.compile(
            r"(?:const|let|var)\s+(\w+)\s*=\s*",
            re.MULTILINE,
        )

        for match in var_pattern.finditer(script_text):
            var_name = match.group(1)
            start_pos = match.end()

            if start_pos >= len(script_text):
                continue

            # Find the opening brace/bracket
            first_char = script_text[start_pos:].lstrip()[0:1]
            if first_char not in ("{", "["):
                continue

            # Find matching close brace/bracket
            adjusted_start = (
                start_pos
                + len(script_text[start_pos:])
                - len(script_text[start_pos:].lstrip())
            )
            obj_literal = self._extract_balanced_braces(
                script_text, adjusted_start, first_char
            )
            if obj_literal:
                results.append((var_name, obj_literal))

        return results

    @staticmethod
    def _extract_balanced_braces(text: str, start: int, open_char: str) -> str | None:
        """
        Extract a balanced brace/bracket expression from text.

        Args:
            text: Full text
            start: Starting position (at the opening brace/bracket)
            open_char: The opening character ('{' or '[')

        Returns:
            The balanced expression including braces, or None if unbalanced
        """
        close_char = "}" if open_char == "{" else "]"
        depth = 0
        in_string = False
        string_char = None
        escape_next = False
        i = start

        while i < len(text):
            char = text[i]

            if escape_next:
                escape_next = False
                i += 1
                continue

            if char == "\\":
                escape_next = True
                i += 1
                continue

            if in_string:
                if char == string_char:
                    in_string = False
            elif char in ('"', "'"):
                in_string = True
                string_char = char
            elif char == open_char:
                depth += 1
            elif char == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]

            i += 1

        return None

    @staticmethod
    def _serialize_python_dict(data: dict | list, original_text: str) -> str:
        """
        Serialize a Python dict/list back to string, preserving formatting.

        Attempts to detect whether the original used single or double quotes
        and maintains that style.

        Args:
            data: The dictionary or list to serialize
            original_text: The original text to detect formatting style from

        Returns:
            Serialized string representation
        """
        # Detect if original used single quotes predominantly
        single_quote_count = original_text.count("'")
        double_quote_count = original_text.count('"')
        use_single_quotes = single_quote_count > double_quote_count

        # Use repr which gives Python literal syntax
        result = repr(data)

        # If original used double quotes but repr uses single, swap them
        # (repr typically uses single quotes)
        if not use_single_quotes:
            # Simple swap - this works for most cases without nested quotes
            result = result.replace("'", '"')

        return result

    def _extract_dict_units(  # noqa: C901
        self,
        el: etree._Element,
        xpath: str,
    ) -> tuple[list[str], list[_TranslationUnitRef]]:
        """
        Extract translatable string values from dict content in a script tag.

        Supports both JSON and Python dictionary syntax.
        Recursively walks the structure and extracts all string values
        that appear to be translatable text (not URLs, identifiers, etc.).

        Returns:
            Tuple of (units, refs) for all translatable strings in the dictionary
        """
        units: list[str] = []
        refs: list[_TranslationUnitRef] = []

        if not el.text:
            return units, refs

        # Try parsing as Python dict first, then fall back to JSON
        data = self._parse_python_dict(el.text)
        if data is None:
            try:
                data = json.loads(el.text)
            except json.JSONDecodeError:
                return units, refs

        def extract_from_value(
            value: str | dict | list, path: tuple[str | int, ...]
        ) -> None:
            """Recursively extract translatable strings from value."""
            if isinstance(value, str):
                _leading, core, _trailing = self._split_preserve_outer_ws(value)
                if core.strip() and not self._looks_like_nontranslatable(core):
                    units.append(core)
                    refs.append(
                        _TranslationUnitRef(
                            kind="dict_value",
                            xpath=xpath,
                            json_path=path,
                        )
                    )
            elif isinstance(value, dict):
                for key, val in value.items():
                    extract_from_value(val, (*path, key))
            elif isinstance(value, list):
                for idx, item in enumerate(value):
                    extract_from_value(item, (*path, idx))

        extract_from_value(data, ())
        return units, refs

    def _extract_js_dict_units(  # noqa: C901
        self,
        el: etree._Element,
        xpath: str,
    ) -> tuple[list[str], list[_TranslationUnitRef]]:
        """
        Extract translatable keys and values from JS object literals in a script tag.

        Finds variable assignments like `const glossaryData = {...}` and extracts
        translatable string keys and values from the object literals.

        Returns:
            Tuple of (units, refs) for all translatable strings in JS objects
        """
        units: list[str] = []
        refs: list[_TranslationUnitRef] = []

        if not el.text:
            return units, refs

        # Extract object literals from JS variable assignments
        js_objects = self._extract_js_object_literals(el.text)

        for var_name, obj_literal in js_objects:
            # Convert JS syntax to Python and parse
            python_literal = self._convert_js_to_python_literal(obj_literal)
            data = self._parse_python_dict(python_literal)

            if data is None:
                # Try parsing as JSON as fallback
                try:
                    data = json.loads(obj_literal)
                except json.JSONDecodeError:
                    continue

            def extract_from_container(  # noqa: C901
                container: dict | list,
                path: tuple[str | int, ...],
                vname: str,
            ) -> None:
                """Recursively extract translatable keys and values."""
                if isinstance(container, dict):
                    for key, val in container.items():
                        # Extract the key itself if it's a translatable string
                        if isinstance(key, str):
                            _leading, core, _trailing = self._split_preserve_outer_ws(
                                key
                            )
                            if core.strip() and not self._looks_like_nontranslatable(
                                core
                            ):
                                units.append(core)
                                refs.append(
                                    _TranslationUnitRef(
                                        kind="js_dict_key",
                                        xpath=xpath,
                                        json_path=(*path, key),
                                        js_var_name=vname,
                                    )
                                )
                        # Extract the value
                        if isinstance(val, str):
                            _leading, core, _trailing = self._split_preserve_outer_ws(
                                val
                            )
                            if core.strip() and not self._looks_like_nontranslatable(
                                core
                            ):
                                units.append(core)
                                refs.append(
                                    _TranslationUnitRef(
                                        kind="js_dict_value",
                                        xpath=xpath,
                                        json_path=(*path, key),
                                        js_var_name=vname,
                                    )
                                )
                        elif isinstance(val, (dict, list)):
                            extract_from_container(val, (*path, key), vname)
                elif isinstance(container, list):
                    for idx, item in enumerate(container):
                        if isinstance(item, str):
                            _leading, core, _trailing = self._split_preserve_outer_ws(
                                item
                            )
                            if core.strip() and not self._looks_like_nontranslatable(
                                core
                            ):
                                units.append(core)
                                refs.append(
                                    _TranslationUnitRef(
                                        kind="js_dict_value",
                                        xpath=xpath,
                                        json_path=(*path, idx),
                                        js_var_name=vname,
                                    )
                                )
                        elif isinstance(item, (dict, list)):
                            extract_from_container(item, (*path, idx), vname)

            extract_from_container(data, (), var_name)

        return units, refs

    def _should_translate_text_in_element(self, el: etree._Element) -> bool:
        return (el.tag or "").lower() not in self._SKIP_TEXT_TAGS

    @staticmethod
    def _looks_like_nontranslatable(value: str) -> bool:
        v = value.strip()
        if not v:
            return True
        # Avoid translating obvious identifiers/paths/urls
        if "://" in v or v.startswith(("/", "./")):
            return True
        if v.startswith("#") and len(v) > 1:
            return True
        # Avoid translating pure tokens/codes
        if re.fullmatch(r"[A-Za-z0-9_\-.:/]+", v) and not re.search(r"[A-Za-z]", v):  # noqa: SIM103
            return True
        return False

    def extract_units(  # noqa: C901, PLR0912
        self, raw: str
    ) -> tuple[etree._Element, list[str], list[_TranslationUnitRef]]:
        """
        Parse markup and extract a list of dedicated translation units.

        Returns:
            (root, units, refs)
            - root: parsed lxml element tree root
            - units: list of *core* strings to translate (trimmed, no outer ws)
            - refs: parallel list of references describing where each unit belongs
        """
        root = self.parse(raw)

        units: list[str] = []
        refs: list[_TranslationUnitRef] = []

        def add_unit(text: str, ref: _TranslationUnitRef) -> None:
            if text is None:
                return
            _leading, core, _trailing = self._split_preserve_outer_ws(text)
            if not core.strip():
                return
            if self._looks_like_nontranslatable(core):
                return
            # Store only core; outer whitespace is preserved on reinsertion
            units.append(core)
            refs.append(ref)

        tree = root.getroottree()

        for el in self._iter_elements(root):
            xpath = tree.getpath(el)

            # Handle pure data script tags (JSON, Python dict)
            if self._is_data_script(el):
                dict_units, dict_refs = self._extract_dict_units(el, xpath)
                units.extend(dict_units)
                refs.extend(dict_refs)
                # Also process tail text for script tags
                if el.tail:
                    add_unit(el.tail, _TranslationUnitRef("tail", xpath))
                continue

            # Handle JavaScript scripts with object literals
            if self._is_js_script_with_dict(el):
                js_units, js_refs = self._extract_js_dict_units(el, xpath)
                units.extend(js_units)
                refs.extend(js_refs)
                # Also process tail text for script tags
                if el.tail:
                    add_unit(el.tail, _TranslationUnitRef("tail", xpath))
                continue

            # Text node
            if self._should_translate_text_in_element(el):
                if el.text:
                    add_unit(el.text, _TranslationUnitRef("text", xpath))
                if el.tail:
                    add_unit(el.tail, _TranslationUnitRef("tail", xpath))

            # Attribute values
            for attr_name, attr_val in list(el.attrib.items()):
                if not attr_val:
                    continue
                if not self._is_translatable_attr(el, attr_name):
                    continue
                _leading, core, _trailing = self._split_preserve_outer_ws(attr_val)
                if not core.strip():
                    continue
                if self._looks_like_nontranslatable(core):
                    continue
                add_unit(
                    attr_val,
                    _TranslationUnitRef("attr", xpath, attr_name=attr_name),
                )

        return root, units, refs

    def _apply_dict_translation(  # noqa: C901, PLR0912
        self,
        el: etree._Element,
        dict_path: tuple[str | int, ...],
        translated_core: str,
    ) -> None:
        """
        Apply a translation to a path within dictionary content of a script tag.

        Supports both Python dict syntax and JSON.

        Args:
            el: The script element containing the dictionary
            dict_path: Tuple of keys/indices to navigate to the value
            translated_core: The translated string to insert
        """
        if not el.text:
            return

        original_text = el.text

        # Try parsing as Python dict first, then fall back to JSON
        data = self._parse_python_dict(original_text)
        is_python_dict = data is not None

        if data is None:
            try:
                data = json.loads(original_text)
            except json.JSONDecodeError:
                return

        # Navigate to the parent of the target value
        current: dict | list = data
        for key in dict_path[:-1]:
            if isinstance(current, dict) and key in current:  # noqa: SIM114
                current = current[key]
            elif (
                isinstance(current, list)
                and isinstance(key, int)
                and 0 <= key < len(current)
            ):
                current = current[key]
            else:
                return  # Path not found

        # Apply translation preserving whitespace
        final_key = dict_path[-1]
        if isinstance(current, dict) and final_key in current:  # noqa: SIM114
            orig = current[final_key]
            if isinstance(orig, str):
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                current[final_key] = f"{leading}{translated_core}{trailing}"
        elif (
            isinstance(current, list)
            and isinstance(final_key, int)
            and 0 <= final_key < len(current)
        ):
            orig = current[final_key]
            if isinstance(orig, str):
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                current[final_key] = f"{leading}{translated_core}{trailing}"

        # Serialize back using appropriate format
        if is_python_dict:
            el.text = self._serialize_python_dict(data, original_text)
        else:
            el.text = json.dumps(data, ensure_ascii=False, indent=2)

    def _apply_js_dict_translation(  # noqa: C901, PLR0912
        self,
        el: etree._Element,
        var_name: str,
        dict_path: tuple[str | int, ...],
        translated_core: str,
    ) -> None:
        """
        Apply a translation to a value within a JavaScript object literal.

        Finds the variable assignment, parses the object, updates the value,
        and replaces the object literal in the original script.

        Args:
            el: The script element containing JavaScript
            var_name: The variable name holding the object
            dict_path: Tuple of keys/indices to navigate to the value
            translated_core: The translated string to insert
        """
        if not el.text:
            return

        original_text = el.text

        # Find this specific variable's object literal
        js_objects = self._extract_js_object_literals(original_text)
        target_literal = None
        for vname, obj_literal in js_objects:
            if vname == var_name:
                target_literal = obj_literal
                break

        if target_literal is None:
            return

        # Parse the object
        python_literal = self._convert_js_to_python_literal(target_literal)
        data = self._parse_python_dict(python_literal)

        if data is None:
            try:
                data = json.loads(target_literal)
            except json.JSONDecodeError:
                return

        # Navigate to the parent of the target value
        current: dict | list = data
        for key in dict_path[:-1]:
            if isinstance(current, dict) and key in current:  # noqa: SIM114
                current = current[key]
            elif (
                isinstance(current, list)
                and isinstance(key, int)
                and 0 <= key < len(current)
            ):
                current = current[key]
            else:
                return  # Path not found

        # Apply translation preserving whitespace
        final_key = dict_path[-1]
        if isinstance(current, dict) and final_key in current:  # noqa: SIM114
            orig = current[final_key]
            if isinstance(orig, str):
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                current[final_key] = f"{leading}{translated_core}{trailing}"
        elif (
            isinstance(current, list)
            and isinstance(final_key, int)
            and 0 <= final_key < len(current)
        ):
            orig = current[final_key]
            if isinstance(orig, str):
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                current[final_key] = f"{leading}{translated_core}{trailing}"

        # Serialize back to JSON format (works as valid JS)
        new_literal = json.dumps(data, ensure_ascii=False, indent=2)

        # Replace the old literal with the new one in the script
        el.text = original_text.replace(target_literal, new_literal, 1)

    def _apply_js_dict_key_translation(  # noqa: C901, PLR0912
        self,
        el: etree._Element,
        var_name: str,
        dict_path: tuple[str | int, ...],
        translated_core: str,
    ) -> None:
        """
        Apply a translation to a key within a JavaScript object literal.

        Finds the variable assignment, parses the object, renames the key,
        and replaces the object literal in the original script.

        Args:
            el: The script element containing JavaScript
            var_name: The variable name holding the object
            dict_path: Tuple of keys/indices where the last element is the key to rename
            translated_core: The translated key name
        """
        if not el.text or not dict_path:
            return

        original_text = el.text

        # Find this specific variable's object literal
        js_objects = self._extract_js_object_literals(original_text)
        target_literal = None
        for vname, obj_literal in js_objects:
            if vname == var_name:
                target_literal = obj_literal
                break

        if target_literal is None:
            return

        # Parse the object
        python_literal = self._convert_js_to_python_literal(target_literal)
        data = self._parse_python_dict(python_literal)

        if data is None:
            try:
                data = json.loads(target_literal)
            except json.JSONDecodeError:
                return

        # Navigate to the parent dict containing the key to rename
        current: dict | list = data
        for key in dict_path[:-1]:
            if isinstance(current, dict) and key in current:  # noqa: SIM114
                current = current[key]
            elif (
                isinstance(current, list)
                and isinstance(key, int)
                and 0 <= key < len(current)
            ):
                current = current[key]
            else:
                return  # Path not found

        # Rename the key (only works for dict, not list)
        old_key = dict_path[-1]
        if not isinstance(current, dict) or old_key not in current:
            return

        # Preserve the original key's whitespace in the translated version
        if isinstance(old_key, str):
            leading, _, trailing = self._split_preserve_outer_ws(old_key)
            new_key = f"{leading}{translated_core}{trailing}"
        else:
            new_key = translated_core

        # Create new dict with renamed key while preserving order
        new_dict: dict = {}
        for k, v in current.items():
            if k == old_key:
                new_dict[new_key] = v
            else:
                new_dict[k] = v

        # Update the parent to use the new dict
        if dict_path[:-1]:
            # Navigate to grandparent and update parent reference
            grandparent: dict | list = data
            for key in dict_path[:-2]:
                if isinstance(grandparent, dict) and key in grandparent:  # noqa: SIM114
                    grandparent = grandparent[key]
                elif isinstance(grandparent, list) and isinstance(key, int):
                    grandparent = grandparent[key]
            parent_key = dict_path[-2]
            if isinstance(grandparent, dict):  # noqa: SIM114
                grandparent[parent_key] = new_dict
            elif isinstance(grandparent, list) and isinstance(parent_key, int):
                grandparent[parent_key] = new_dict
        # The key is at root level, replace data entirely
        elif isinstance(data, dict):
            data.clear()
            data.update(new_dict)

        # Serialize back to JSON format (works as valid JS)
        new_literal = json.dumps(data, ensure_ascii=False, indent=2)

        # Replace the old literal with the new one in the script
        el.text = original_text.replace(target_literal, new_literal, 1)

    def apply_translations(  # noqa: C901, PLR0912, PLR0915
        self,
        root: etree._Element,
        refs: list[_TranslationUnitRef],
        translated_units: list[str],
    ) -> etree._Element:
        """
        Reinsert translated units back into the parsed DOM.

        `translated_units` must align 1:1 with `refs` from `extract_units()`.
        Leading/trailing whitespace from the original node/value is preserved.
        """
        if len(refs) != len(translated_units):
            raise ValueError("Translation unit count mismatch")  # noqa: TRY003, EM101

        tree = root.getroottree()

        # Group dictionary translations by xpath to apply them in batch
        dict_translations: dict[str, list[tuple[_TranslationUnitRef, str]]] = {}
        # Group JS dictionary translations by xpath and var_name
        js_dict_translations: dict[str, list[tuple[_TranslationUnitRef, str]]] = {}
        # Group JS dict key translations (applied after values)
        js_dict_key_translations: dict[str, list[tuple[_TranslationUnitRef, str]]] = {}

        for ref, translated_core in zip(refs, translated_units, strict=True):
            if ref.kind == "dict_value" and ref.json_path is not None:
                if ref.xpath not in dict_translations:
                    dict_translations[ref.xpath] = []
                dict_translations[ref.xpath].append((ref, translated_core))
                continue

            if ref.kind == "js_dict_key" and ref.json_path is not None:
                if ref.xpath not in js_dict_key_translations:
                    js_dict_key_translations[ref.xpath] = []
                js_dict_key_translations[ref.xpath].append((ref, translated_core))
                continue

            if ref.kind == "js_dict_value" and ref.json_path is not None:
                if ref.xpath not in js_dict_translations:
                    js_dict_translations[ref.xpath] = []
                js_dict_translations[ref.xpath].append((ref, translated_core))
                continue

            nodes = tree.xpath(ref.xpath)
            if not nodes:
                continue
            el = nodes[0]

            if ref.kind == "text":
                orig = el.text or ""
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                el.text = f"{leading}{translated_core}{trailing}"
            elif ref.kind == "tail":
                orig = el.tail or ""
                leading, _, trailing = self._split_preserve_outer_ws(orig)
                el.tail = f"{leading}{translated_core}{trailing}"
            elif ref.kind == "attr" and ref.attr_name:
                if ref.attr_name in el.attrib:
                    orig = el.attrib.get(ref.attr_name, "")
                    leading, _, trailing = self._split_preserve_outer_ws(orig)
                    el.attrib[ref.attr_name] = f"{leading}{translated_core}{trailing}"
            else:
                continue

        # Apply dictionary translations (Python dict or JSON in script tags)
        for xpath, translations in dict_translations.items():
            nodes = tree.xpath(xpath)
            if not nodes:
                continue
            el = nodes[0]
            for ref, translated_core in translations:
                if ref.json_path is not None:
                    self._apply_dict_translation(el, ref.json_path, translated_core)

        # Apply JavaScript dictionary value translations first
        for xpath, translations in js_dict_translations.items():
            nodes = tree.xpath(xpath)
            if not nodes:
                continue
            el = nodes[0]
            for ref, translated_core in translations:
                if ref.json_path is not None and ref.js_var_name is not None:
                    self._apply_js_dict_translation(
                        el, ref.js_var_name, ref.json_path, translated_core
                    )

        # Apply JavaScript dictionary key translations after values
        # (renaming keys changes the structure, so we do this last)
        for xpath, translations in js_dict_key_translations.items():
            nodes = tree.xpath(xpath)
            if not nodes:
                continue
            el = nodes[0]
            for ref, translated_core in translations:
                if ref.json_path is not None and ref.js_var_name is not None:
                    self._apply_js_dict_key_translation(
                        el, ref.js_var_name, ref.json_path, translated_core
                    )

        return root

    def serialize(self, root: etree._Element) -> str:
        """
        Serialize the DOM back to markup.

        For HTML parsing, lxml frequently wraps content in <html><body>.
        If a <body> exists, this returns its inner HTML to better match original
        fragment inputs while keeping structure valid.
        """
        if not self.is_xml:
            body = root.find(".//body")
            if body is not None:
                parts: list[str] = []
                if body.text:
                    parts.append(body.text)
                for child in body:
                    parts.append(  # noqa: PERF401
                        etree.tostring(child, encoding="unicode", method="html")
                    )
                return "".join(parts)

        return etree.tostring(
            root,
            encoding="unicode",
            method="xml" if self.is_xml else "html",
        )


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


def _normalize_for_glossary_match(value: str) -> str:
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

    corpus = _normalize_for_glossary_match(
        " ".join((s.content or "") for s in subtitles)
    )
    if not corpus:
        return {}

    # Compile patterns once per glossary entry (helps for large glossaries).
    compiled: list[tuple[str, str, re.Pattern[str]]] = []
    for term, translation in glossary.items():
        norm_term = _normalize_for_glossary_match(term)
        if not norm_term:
            continue
        compiled.append(
            (
                term,
                translation,
                re.compile(rf"(?<!\w){re.escape(norm_term)}(?!\w)"),
            )
        )

    return {
        term: translation
        for term, translation, pattern in compiled
        if pattern.search(corpus)
    }


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

    glossary_file_path = glossary_dir_path / f"{target_language}.txt"
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


class LanguageCode:
    """
    Utility class for handling language code conversions between
    Django/Open edX style and BCP47.
    """

    def __init__(self, lang_code):
        self.lang_code = lang_code

    def to_bcp47(self) -> str:
        """
        Convert Django / Open edX style language codes to BCP47.

        Examples:
            zh_HANS     -> zh-Hans
            zh_HANT     -> zh-Hant
            zh_HANS_CN  -> zh-Hans-CN
            en_US       -> en-US
            es_419      -> es-419
            pt_br       -> pt-BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []
        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script (Hans, Hant, Latn, Cyrl, etc.)
                result.append(part.title())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region i.e US, PK, CN
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region (419)
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "-".join(result)

    def to_django(self) -> str:
        """
        Convert BCP47 language tags to Django / Open edX style.

        Examples:
            zh-Hans     -> zh_HANS
            zh-Hant     -> zh_HANT
            zh-Hans-CN  -> zh_HANS_CN
            en-US       -> en_US
            es-419      -> es_419
            pt-BR       -> pt_BR
        """
        if not self.lang_code:
            return self.lang_code

        parts = self.lang_code.replace("_", "-").split("-")
        result = []

        for idx, part in enumerate(parts):
            if idx == 0:
                # Language
                result.append(part.lower())

            elif re.fullmatch(r"[A-Za-z]{4}", part):
                # Script
                result.append(part.upper())

            elif re.fullmatch(r"[A-Za-z]{2}", part):
                # Region
                result.append(part.upper())

            elif re.fullmatch(r"\d{3}", part):
                # Numeric region
                result.append(part)

            else:
                # Variants/extensions
                result.append(part.lower())

        return "_".join(result)
