"""
Management command to translate course content to a specified language.
"""

import json
import logging
import re
import shutil
import tarfile
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ol_openedx_course_translations.providers.deepl_provider import DeepLProvider
from ol_openedx_course_translations.providers.llm_provider import (
    GeminiProvider,
    MistralProvider,
    OpenAIProvider,
)

logger = logging.getLogger(__name__)

# Error messages as constants
DEEPL_API_KEY_MISSING = (
    "DEEPL_API_KEY setting is required for DeepL"  # pragma: allowlist secret
)
OPENAI_API_KEY_MISSING = (
    "OPENAI_API_KEY setting is required for OpenAI"  # pragma: allowlist secret
)
GEMINI_API_KEY_MISSING = (
    "GEMINI_API_KEY setting is required for Gemini"  # pragma: allowlist secret
)
MISTRAL_API_KEY_MISSING = (
    "MISTRAL_API_KEY setting is required for Mistral"  # pragma: allowlist secret
)


class Command(BaseCommand):
    """Translate given course content to the specified language."""

    help = "Translate course content to the specified language."

    def add_arguments(self, parser) -> None:
        """Entry point for subclassed commands to add custom arguments."""
        parser.add_argument(
            "--source-language",
            dest="source_language",
            default="EN",
            help=(
                "Specify the source language of the course content "
                "in ISO format, e.g. `EN` for English."
            ),
        )
        parser.add_argument(
            "--translation-language",
            dest="target_language",
            required=True,
            help=(
                "Specify the language code in ISO format "
                "to translate the course content into. e.g `AR` for Arabic"
            ),
        )
        parser.add_argument(
            "--course-dir",
            dest="course_archive_path",
            required=True,
            help="Specify the course directory (tar archive).",
        )
        parser.add_argument(
            "--xmltranslation",
            dest="xml_translation_provider",
            required=True,
            choices=["deepl", "gemini", "mistral", "openai"],
            help="AI model to use for XML/HTML and text translation.",
        )
        parser.add_argument(
            "--srttranslations",
            dest="srt_translation_provider",
            required=True,
            choices=["deepl", "gemini", "mistral", "openai"],
            help="AI model to use for SRT subtitle translation.",
        )
        parser.add_argument(
            "--glossaryfile",
            dest="glossary_directory",
            required=False,
            help=(
                "Path to glossary directory containing "
                "language-specific glossary files."
            ),
        )

    def handle(self, **options) -> None:
        """Handle the translate_course command."""
        try:
            self._validate_inputs(options)

            course_archive_path = Path(options["course_archive_path"])
            source_language = options["source_language"]
            target_language = options["target_language"]
            xml_provider_name = options["xml_translation_provider"]
            srt_provider_name = options["srt_translation_provider"]
            glossary_directory = options.get("glossary_directory")

            # Initialize providers
            self.xml_provider = self._get_provider(xml_provider_name)
            self.srt_provider = self._get_provider(srt_provider_name)
            self.glossary_directory = glossary_directory

            # Extract course archive
            extracted_course_dir = self._extract_course_archive(course_archive_path)

            # Create translated copy
            translated_course_dir = self._create_translated_copy(
                extracted_course_dir, target_language
            )

            # Delete extracted directory after copying
            if extracted_course_dir.exists():
                shutil.rmtree(extracted_course_dir)

            # Translate content
            self._translate_course_content(
                translated_course_dir, source_language, target_language
            )

            # Create final archive
            translated_archive_path = self._create_translated_archive(
                translated_course_dir, target_language, course_archive_path.stem
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Translation completed. Archive created: {translated_archive_path}"
                )
            )

        except Exception as e:
            logger.exception("Translation failed")
            error_msg = f"Translation failed: {e}"
            raise CommandError(error_msg) from e

    def _get_provider(self, provider_name: str):
        """Get translation provider based on provider name."""
        openai_api_key = getattr(settings, "OPENAI_API_KEY", "")

        if provider_name == "deepl":
            deepl_api_key = getattr(settings, "DEEPL_API_KEY", "")
            if not deepl_api_key:
                raise CommandError(DEEPL_API_KEY_MISSING)
            return DeepLProvider(deepl_api_key, openai_api_key)

        elif provider_name == "openai":
            if not openai_api_key:
                raise CommandError(OPENAI_API_KEY_MISSING)
            return OpenAIProvider(openai_api_key, openai_api_key)

        elif provider_name == "gemini":
            gemini_api_key = getattr(settings, "GEMINI_API_KEY", "")
            if not gemini_api_key:
                raise CommandError(GEMINI_API_KEY_MISSING)
            return GeminiProvider(gemini_api_key, openai_api_key)

        elif provider_name == "mistral":
            mistral_api_key = getattr(settings, "MISTRAL_API_KEY", "")
            if not mistral_api_key:
                raise CommandError(MISTRAL_API_KEY_MISSING)
            return MistralProvider(mistral_api_key, openai_api_key)

        else:
            error_msg = f"Unknown provider: {provider_name}"
            raise CommandError(error_msg)

    def get_supported_archive_extension(self, filename: str) -> str | None:
        """
        Return the supported archive extension if filename ends with one, else None.
        """
        for ext in settings.COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS:
            if filename.endswith(ext):
                return ext
        return None

    def _validate_inputs(self, options: dict[str, Any]) -> None:
        """Validate command inputs."""
        course_archive_path = Path(options["course_archive_path"])

        if not course_archive_path.exists():
            error_msg = f"Course archive not found: {course_archive_path}"
            raise CommandError(error_msg)

        if self.get_supported_archive_extension(course_archive_path.name) is None:
            supported_extensions = ", ".join(
                settings.COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS
            )
            error_msg = f"Course archive must be a tar file: {supported_extensions}"
            raise CommandError(error_msg)

    def _extract_course_archive(self, course_archive_path: Path) -> Path:
        """Extract course archive to working directory."""
        # Use the parent directory of the source file as the base extraction directory
        extraction_base_dir = course_archive_path.parent

        # Get base name without extension
        archive_extension = self.get_supported_archive_extension(
            course_archive_path.name
        )
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
                    self._validate_tar_file(tar_file)
                    tar_file.extractall(path=extracted_course_dir, filter="data")
            except (tarfile.TarError, OSError) as e:
                error_msg = f"Failed to extract archive: {e}"
                raise CommandError(error_msg) from e

        logger.info("Extracted course to: %s", extracted_course_dir)
        return extracted_course_dir

    def _validate_tar_file(self, tar_file: tarfile.TarFile) -> None:
        """Validate tar file contents for security."""
        for tar_member in tar_file.getmembers():
            # Check for directory traversal attacks
            if tar_member.name.startswith("/") or ".." in tar_member.name:
                error_msg = f"Unsafe tar member: {tar_member.name}"
                raise CommandError(error_msg)
            # Check for excessively large files
            if tar_member.size > 512 * 1024 * 1024:  # 0.5GB limit
                error_msg = f"File too large: {tar_member.name}"
                raise CommandError(error_msg)

    def _create_translated_copy(
        self, source_course_dir: Path, target_language: str
    ) -> Path:
        """Create a copy of the course for translation."""
        source_base_name = source_course_dir.name
        translated_dir_name = f"{target_language}_{source_base_name}"
        translated_course_dir = source_course_dir.parent / translated_dir_name

        if translated_course_dir.exists():
            error_msg = f"Translation directory already exists: {translated_course_dir}"
            raise CommandError(error_msg)

        shutil.copytree(source_course_dir, translated_course_dir)
        logger.info("Created translation copy: %s", translated_course_dir)
        return translated_course_dir

    def _translate_course_content(
        self, course_dir: Path, source_language: str, target_language: str
    ) -> None:
        """Translate all course content."""
        # Translate files in main directories
        for search_directory in [course_dir, course_dir.parent]:
            self._translate_files_in_directory(
                search_directory, source_language, target_language, recursive=False
            )

            # Translate files in target subdirectories
            for target_dir_name in settings.COURSE_TRANSLATIONS_TARGET_DIRECTORIES:
                target_directory = search_directory / target_dir_name
                if target_directory.exists() and target_directory.is_dir():
                    self._translate_files_in_directory(
                        target_directory,
                        source_language,
                        target_language,
                        recursive=True,
                    )

        # Translate special JSON files
        self._translate_grading_policy(course_dir, target_language)
        self._translate_policy_json(course_dir, target_language)

    def _translate_files_in_directory(
        self,
        directory_path: Path,
        source_language: str,
        target_language: str,
        *,
        recursive: bool = False,
    ) -> None:
        """Translate files in a directory."""
        if recursive:
            translatable_file_paths: list[Path] = []
            for file_extension in settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS:
                translatable_file_paths.extend(
                    directory_path.rglob(f"*{file_extension}")
                )
        else:
            translatable_file_paths = [
                file_path
                for file_path in directory_path.iterdir()
                if file_path.is_file()
                and any(
                    file_path.name.endswith(extension)
                    for extension in (
                        settings.COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS
                    )
                )
            ]

        for translatable_file_path in translatable_file_paths:
            try:
                self._translate_file(
                    translatable_file_path, source_language, target_language
                )
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Failed to translate %s: %s", translatable_file_path, e)

    def _update_video_xml(self, xml_content: str, target_language: str) -> str:  # noqa: C901
        """Update video XML transcripts and transcript tags for the target language."""
        try:
            xml_root = ElementTree.fromstring(xml_content)
            target_lang_code = target_language.lower()

            # Update transcripts attribute in <video>
            if xml_root.tag == "video" and "transcripts" in xml_root.attrib:
                transcripts_json_str = xml_root.attrib["transcripts"].replace(
                    "&quot;", '"'
                )
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
                updated_transcripts_json = json.dumps(
                    transcripts_dict, ensure_ascii=False
                )
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

            xml_content = ElementTree.tostring(xml_root, encoding="unicode")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to update transcripts in video XML: %s", e)

        return xml_content

    def _translate_file(
        self, file_path: Path, source_language: str, target_language: str
    ) -> None:
        """Translate a single file."""
        # Handle SRT files with SRT provider
        if file_path.suffix == ".srt":
            try:
                self._translate_srt_file_with_provider(
                    file_path, source_language, target_language
                )
            except (OSError, ValueError) as e:
                logger.warning("Failed to translate SRT %s: %s", file_path, e)
            return

        try:
            file_content = file_path.read_text(encoding="utf-8")
            logger.debug("Translating: %s", file_path)

            # Use XML provider for all other content
            tag_handling_mode = None
            if file_path.suffix in [".xml", ".html"]:
                tag_handling_mode = file_path.suffix.lstrip(".")

            translated_file_content = self.xml_provider.translate_text(
                file_content,
                target_language.lower(),
                tag_handling=tag_handling_mode,
                glossary_file=self.glossary_directory,
            )

            # Handle XML display_name translation
            if file_path.suffix == ".xml":
                translated_file_content = self._translate_display_name(
                    translated_file_content, target_language
                )

                # If parent directory is 'video', update transcripts attribute
                if file_path.parent.name == "video":
                    translated_file_content = self._update_video_xml(
                        translated_file_content, target_language
                    )

            file_path.write_text(translated_file_content, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to translate %s: %s", file_path, e)

    def _translate_srt_file_with_provider(
        self, srt_file_path: Path, source_language: str, target_language: str
    ) -> None:
        """Translate an SRT file using the configured SRT provider."""
        self.srt_provider.translate_document(
            srt_file_path, srt_file_path, source_language, target_language
        )

    def _translate_text(
        self,
        input_text: str,
        target_language: str,
        source_filename: str | None = None,
    ) -> str:
        """Translate text using XML provider."""
        if not input_text or not input_text.strip():
            return input_text

        tag_handling_mode = None
        if source_filename:
            file_extension = Path(source_filename).suffix.lstrip(".")
            if file_extension in ["html", "xml"]:
                tag_handling_mode = file_extension

        try:
            return self.xml_provider.translate_text(
                input_text,
                target_language.lower(),
                tag_handling=tag_handling_mode,
                glossary_file=self.glossary_directory,
            )
        except (OSError, ValueError) as e:
            logger.warning(
                "Translation failed for text: %s... Error: %s", input_text[:50], e
            )
            return input_text

    def _translate_grading_policy(self, course_dir: Path, target_language: str) -> None:
        """Translate grading_policy.json files."""
        course_policies_dir = course_dir / "course" / "policies"

        if not course_policies_dir.exists():
            return

        for policy_child_dir in course_policies_dir.iterdir():
            if not policy_child_dir.is_dir():
                continue

            grading_policy_file_path = policy_child_dir / "grading_policy.json"
            if not grading_policy_file_path.exists():
                continue

            try:
                grading_policy_data = json.loads(
                    grading_policy_file_path.read_text(encoding="utf-8")
                )
                policy_updated = False

                for grader_item in grading_policy_data.get("GRADER", []):
                    if "short_label" in grader_item:
                        translated_short_label = self._translate_text(
                            grader_item["short_label"], target_language
                        )
                        grader_item["short_label"] = translated_short_label
                        policy_updated = True

                if policy_updated:
                    grading_policy_file_path.write_text(
                        json.dumps(grading_policy_data, ensure_ascii=False, indent=4),
                        encoding="utf-8",
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Failed to translate grading policy in %s: %s", policy_child_dir, e
                )

    def _translate_policy_json(self, course_dir: Path, target_language: str) -> None:
        """Translate policy.json files."""
        course_policies_dir = course_dir / "course" / "policies"

        if not course_policies_dir.exists():
            return

        for policy_child_dir in course_policies_dir.iterdir():
            if not policy_child_dir.is_dir():
                continue

            policy_file_path = policy_child_dir / "policy.json"
            if not policy_file_path.exists():
                continue

            try:
                policy_json_data = json.loads(
                    policy_file_path.read_text(encoding="utf-8")
                )
                policy_data_updated = False

                for course_policy_obj in policy_json_data.values():
                    if not isinstance(course_policy_obj, dict):
                        continue

                    # Translate various fields
                    fields_updated = self._translate_policy_fields(
                        course_policy_obj, target_language
                    )
                    policy_data_updated = policy_data_updated or fields_updated

                if policy_data_updated:
                    policy_file_path.write_text(
                        json.dumps(policy_json_data, ensure_ascii=False, indent=4),
                        encoding="utf-8",
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Failed to translate policy in %s: %s", policy_child_dir, e
                )

    def _translate_policy_fields(
        self,
        course_policy_obj: dict[str, Any],
        target_language: str,
    ) -> bool:
        """Translate specific fields in policy object."""
        any_field_updated = False

        # Translate simple string fields
        string_fields_updated = self._translate_string_fields(
            course_policy_obj, target_language
        )
        any_field_updated = any_field_updated or string_fields_updated

        # Translate discussion topics
        discussion_topics_updated = self._translate_discussion_topics(
            course_policy_obj, target_language
        )
        any_field_updated = any_field_updated or discussion_topics_updated

        # Translate learning info and tabs
        learning_info_tabs_updated = self._translate_learning_info_and_tabs(
            course_policy_obj, target_language
        )
        any_field_updated = any_field_updated or learning_info_tabs_updated

        # Translate XML attributes
        xml_attributes_updated = self._translate_xml_attributes(
            course_policy_obj, target_language
        )
        return any_field_updated or xml_attributes_updated

    def _translate_string_fields(
        self,
        course_policy_obj: dict[str, Any],
        target_language: str,
    ) -> bool:
        """Translate simple string fields."""
        string_fields_updated = False

        translatable_string_fields = [
            "advertised_start",
            "display_name",
            "display_organization",
        ]
        for field_name in translatable_string_fields:
            if field_name in course_policy_obj:
                translated_field_value = self._translate_text(
                    course_policy_obj[field_name], target_language
                )
                course_policy_obj[field_name] = translated_field_value
                string_fields_updated = True

        return string_fields_updated

    def _translate_discussion_topics(
        self,
        course_policy_obj: dict[str, Any],
        target_language: str,
    ) -> bool:
        """Translate discussion topics."""
        discussion_topics_updated = False

        if "discussion_topics" in course_policy_obj:
            discussion_topics_dict = course_policy_obj["discussion_topics"]
            if isinstance(discussion_topics_dict, dict):
                translated_discussion_topics = {}
                for topic_key, topic_value in discussion_topics_dict.items():
                    translated_topic_key = self._translate_text(
                        topic_key, target_language
                    )
                    translated_discussion_topics[translated_topic_key] = topic_value
                course_policy_obj["discussion_topics"] = translated_discussion_topics
                discussion_topics_updated = True

        return discussion_topics_updated

    def _translate_learning_info_and_tabs(
        self,
        course_policy_obj: dict[str, Any],
        target_language: str,
    ) -> bool:
        """Translate learning info and tabs."""
        learning_info_tabs_updated = False

        # Learning info
        if "learning_info" in course_policy_obj and isinstance(
            course_policy_obj["learning_info"], list
        ):
            translated_learning_info = []
            for learning_info_item in course_policy_obj["learning_info"]:
                translated_info_item = self._translate_text(
                    learning_info_item, target_language
                )
                translated_learning_info.append(translated_info_item)
            course_policy_obj["learning_info"] = translated_learning_info
            learning_info_tabs_updated = True

        # Tabs
        if "tabs" in course_policy_obj and isinstance(course_policy_obj["tabs"], list):
            for tab_obj in course_policy_obj["tabs"]:
                if isinstance(tab_obj, dict) and "name" in tab_obj:
                    translated_tab_name = self._translate_text(
                        tab_obj["name"], target_language
                    )
                    tab_obj["name"] = translated_tab_name
                    learning_info_tabs_updated = True

        return learning_info_tabs_updated

    def _translate_xml_attributes(
        self,
        course_policy_obj: dict[str, Any],
        target_language: str,
    ) -> bool:
        """Translate XML attributes."""
        xml_attributes_updated = False

        if "xml_attributes" in course_policy_obj and isinstance(
            course_policy_obj["xml_attributes"], dict
        ):
            xml_attributes_dict = course_policy_obj["xml_attributes"]
            translatable_xml_fields = [
                "diplay_name",  # Note: keeping typo as in original
                "info_sidebar_name",
            ]
            for xml_field_name in translatable_xml_fields:
                if xml_field_name in xml_attributes_dict:
                    translated_xml_field_value = self._translate_text(
                        xml_attributes_dict[xml_field_name],
                        target_language,
                    )
                    xml_attributes_dict[xml_field_name] = translated_xml_field_value
                    xml_attributes_updated = True

        return xml_attributes_updated

    def _create_translated_archive(
        self,
        translated_course_dir: Path,
        target_language: str,
        original_archive_name: str,
    ) -> Path:
        """Create tar.gz archive of translated course."""
        # Remove all archive extensions from the original name
        archive_extension = self.get_supported_archive_extension(original_archive_name)
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

        # Delete extracted directory after copying
        if translated_course_dir.exists():
            shutil.rmtree(translated_course_dir)

        logger.info("Created tar.gz archive: %s", translated_archive_path)
        return translated_archive_path

    def translate_srt_file(
        self, srt_input_file_path: Path, source_language: str, target_language: str
    ) -> None:
        """
        Translate an SRT file using translation provider.
        Creates a new output file with the target language prefix, then renames
        it to the original file.
        """
        input_filename = srt_input_file_path.name
        output_filename = input_filename
        if "-" in input_filename and input_filename.endswith(".srt"):
            filename_parts = input_filename.rsplit("-", 1)
            output_filename = f"{filename_parts[0]}-{target_language.lower()}.srt"
        srt_output_file_path = srt_input_file_path.parent / output_filename

        # Use available provider for SRT translation
        srt_translation_provider = (
            self._get_provider("deepl")
            if hasattr(settings, "DEEPL_API_KEY") and settings.DEEPL_API_KEY
            else self.srt_provider
        )
        srt_translation_provider.translate_document(
            srt_input_file_path, srt_output_file_path, source_language, target_language
        )

    def _translate_display_name(self, xml_content: str, target_language: str) -> str:
        """Extract and translate the display_name attribute of the root element."""
        try:
            xml_root = ElementTree.fromstring(xml_content)
            display_name_attribute = xml_root.attrib.get("display_name")

            if display_name_attribute:
                translated_display_name = self._translate_text(
                    display_name_attribute, target_language
                )
                xml_root.set("display_name", translated_display_name)
                return ElementTree.tostring(xml_root, encoding="unicode")
        except ElementTree.ParseError as e:
            logger.warning("Could not translate display_name: %s", e)

        return xml_content
