"""Utility functions for course translations.

This module includes DOM-aware helpers for translating HTML/XML safely by:
- Extracting only text nodes and allowlisted attribute VALUES as independent units
- Sending only those units to translation providers (never raw markup blobs)
- Reinserting translations without changing markup structure, tag names,
or attribute names
"""

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
    ES_419_LANGUAGE_CODE,
    ES_LANGUAGE_CODE,
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
        target_lang_code = target_language

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
                glossary_directory=glossary_directory,
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
                    key, target_language.lower(), glossary_directory=glossary_directory
                )
                translated_topics[translated_key] = value
            course_policy_obj["discussion_topics"] = translated_topics

    # Translate learning info
    if "learning_info" in course_policy_obj and isinstance(
        course_policy_obj["learning_info"], list
    ):
        translated_info = [
            provider.translate_text(
                item, target_language.lower(), glossary_directory=glossary_directory
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
                    target_language.lower(),
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
    # Use 'es' for Spanish regardless of es-419
    output_lang_code = (
        ES_LANGUAGE_CODE
        if target_language.lower() == ES_419_LANGUAGE_CODE
        else target_language.lower()
    )

    if "-" in input_filename and input_filename.endswith(".srt"):
        filename_parts = input_filename.rsplit("-", 1)
        return f"{filename_parts[0]}-{output_lang_code}.srt"
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
        target_lang_code = (
            ES_LANGUAGE_CODE
            if target_language.lower() == ES_419_LANGUAGE_CODE
            else target_language.lower()
        )

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
    """

    kind: str
    xpath: str
    attr_name: str | None = None


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

    Limitations:
    - HTML parsing with lxml may normalize malformed HTML; prefer XML/XHTML
    where possible.
    - For HTML fragments, serialization attempts to return the <body> inner HTML.
    """

    # Tags whose text content should not be translated (non-user-visible)
    _SKIP_TEXT_TAGS = {"script", "style"}

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

    def extract_units(  # noqa: C901
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
            # Text node
            if self._should_translate_text_in_element(el):
                if el.text:
                    add_unit(el.text, _TranslationUnitRef("text", tree.getpath(el)))
                if el.tail:
                    add_unit(el.tail, _TranslationUnitRef("tail", tree.getpath(el)))

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
                    _TranslationUnitRef("attr", tree.getpath(el), attr_name=attr_name),
                )

        return root, units, refs

    def apply_translations(
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
        for ref, translated_core in zip(refs, translated_units, strict=True):
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
