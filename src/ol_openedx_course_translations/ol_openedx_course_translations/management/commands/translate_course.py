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

import deepl
from defusedxml import ElementTree
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


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
            dest="translation_language",
            required=True,
            help=(
                "Specify the language code in ISO format "
                "to translate the course content into. e.g `AR` for Arabic"
            ),
        )
        parser.add_argument(
            "--course-dir",
            dest="course_directory",
            required=True,
            help="Specify the course directory (tar archive).",
        )

    def handle(self, **options) -> None:
        """Handle the translate_course command."""
        try:
            self._validate_inputs(options)

            course_dir = Path(options["course_directory"])
            source_language = options["source_language"]
            translation_language = options["translation_language"]

            # Extract course archive
            extracted_dir = self._extract_course_archive(course_dir)

            # Create translated copy
            translated_dir = self._create_translated_copy(
                extracted_dir, translation_language
            )

            # Delete extracted directory after copying
            if extracted_dir.exists():
                shutil.rmtree(extracted_dir)

            # Translate content
            billed_chars = self._translate_course_content(
                translated_dir, source_language, translation_language
            )

            # Create final archive
            archive_path = self._create_translated_archive(
                translated_dir, translation_language, course_dir.stem
            )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Translation completed. Archive created: {archive_path}"
                )
            )
            logger.info("Total billed characters: %s", billed_chars)

        except Exception as e:
            logger.exception("Translation failed")
            error_msg = f"Translation failed: {e}"
            raise CommandError(error_msg) from e

    def get_supported_archive_extension(self, filename: str) -> str | None:
        """
        Return the supported archive extension if filename ends with one, else None.
        """
        for ext in settings.OL_OPENEDX_COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS:
            if filename.endswith(ext):
                return ext
        return None

    def _validate_inputs(self, options: dict[str, Any]) -> None:
        """Validate command inputs."""
        course_dir = Path(options["course_directory"])

        if not course_dir.exists():
            error_msg = f"Course directory not found: {course_dir}"
            raise CommandError(error_msg)

        if self.get_supported_archive_extension(course_dir.name) is None:
            supported_exts = ", ".join(
                settings.OL_OPENEDX_COURSE_TRANSLATIONS_SUPPORTED_ARCHIVE_EXTENSIONS
            )
            error_msg = f"Course directory must be a tar file: {supported_exts}"
            raise CommandError(error_msg)

        if not hasattr(settings, "DEEPL_API_KEY") or not settings.DEEPL_API_KEY:
            error_msg = "DEEPL_API_KEY setting is required"
            raise CommandError(error_msg)

    def _extract_course_archive(self, course_dir: Path) -> Path:
        """Extract course archive to working directory."""
        # Use the parent directory of the source file as the base extraction directory
        extract_base_dir = course_dir.parent

        # Get base name without extension
        ext = self.get_supported_archive_extension(course_dir.name)
        tarball_base = course_dir.name[: -len(ext)] if ext else course_dir.name

        extracted_dir = extract_base_dir / tarball_base

        if not extracted_dir.exists():
            try:
                with tarfile.open(course_dir, "r:*") as tar:
                    # Validate tar file before extraction
                    self._validate_tar_file(tar)
                    tar.extractall(path=extracted_dir, filter="data")
            except (tarfile.TarError, OSError) as e:
                error_msg = f"Failed to extract archive: {e}"
                raise CommandError(error_msg) from e

        logger.info("Extracted course to: %s", extracted_dir)
        return extracted_dir

    def _validate_tar_file(self, tar: tarfile.TarFile) -> None:
        """Validate tar file contents for security."""
        for member in tar.getmembers():
            # Check for directory traversal attacks
            if member.name.startswith("/") or ".." in member.name:
                error_msg = f"Unsafe tar member: {member.name}"
                raise CommandError(error_msg)
            # Check for excessively large files
            if (
                member.size > 512 * 1024 * 1024
            ):  # 0.5GB limit because courses on Production are big
                error_msg = f"File too large: {member.name}"
                raise CommandError(error_msg)

    def _create_translated_copy(
        self, source_dir: Path, translation_language: str
    ) -> Path:
        """Create a copy of the course for translation."""
        base_name = source_dir.name
        new_dir_name = f"{translation_language}_{base_name}"
        new_dir_path = source_dir.parent / new_dir_name

        if new_dir_path.exists():
            error_msg = f"Translation directory already exists: {new_dir_path}"
            raise CommandError(error_msg)

        shutil.copytree(source_dir, new_dir_path)
        logger.info("Created translation copy: %s", new_dir_path)
        return new_dir_path

    def _translate_course_content(
        self, course_dir: Path, source_language: str, translation_language: str
    ) -> int:
        """Translate all course content and return total billed characters."""
        total_billed_chars = 0

        # Translate files in main directories
        for search_dir in [course_dir, course_dir.parent]:
            total_billed_chars += self._translate_files_in_directory(
                search_dir, source_language, translation_language, recursive=False
            )

            # Translate files in target subdirectories
            for dir_name in settings.OL_OPENEDX_COURSE_TRANSLATIONS_TARGET_DIRECTORIES:
                target_dir = search_dir / dir_name
                if target_dir.exists() and target_dir.is_dir():
                    total_billed_chars += self._translate_files_in_directory(
                        target_dir,
                        source_language,
                        translation_language,
                        recursive=True,
                    )

        # Translate special JSON files
        total_billed_chars += self._translate_grading_policy(
            course_dir, source_language, translation_language
        )
        total_billed_chars += self._translate_policy_json(
            course_dir, source_language, translation_language
        )

        return total_billed_chars

    def _translate_files_in_directory(
        self,
        directory: Path,
        source_language: str,
        translation_language: str,
        *,
        recursive: bool = False,
    ) -> int:
        """Translate files in a directory."""
        total_billed_chars = 0

        if recursive:
            file_paths: list[Path] = []
            for ext in settings.OL_OPENEDX_COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS:
                file_paths.extend(directory.rglob(f"*{ext}"))
        else:
            file_paths = [
                f
                for f in directory.iterdir()
                if f.is_file()
                and any(
                    f.name.endswith(ext)
                    for ext in settings.OL_OPENEDX_COURSE_TRANSLATIONS_TRANSLATABLE_EXTENSIONS  # noqa: E501
                )
            ]

        for file_path in file_paths:
            try:
                total_billed_chars += self._translate_file(
                    file_path, source_language, translation_language
                )
            except (OSError, UnicodeDecodeError) as e:
                logger.warning("Failed to translate %s: %s", file_path, e)

        return total_billed_chars

    def _update_video_xml(self, xml_content: str, translation_language: str) -> str:  # noqa: C901
        """Update video XML transcripts and transcript tags for the target language."""
        try:
            root = ElementTree.fromstring(xml_content)
            lang_code = translation_language.lower()

            # Update transcripts attribute in <video>
            if root.tag == "video" and "transcripts" in root.attrib:
                transcripts_json = root.attrib["transcripts"].replace("&quot;", '"')
                transcripts_dict = json.loads(transcripts_json)
                for k in list(transcripts_dict.keys()):
                    value = transcripts_dict[k]
                    new_key = lang_code
                    new_value = re.sub(r"-[a-zA-Z]{2}\.srt$", f"-{new_key}.srt", value)
                    transcripts_dict[new_key] = new_value
                new_transcripts = json.dumps(transcripts_dict, ensure_ascii=False)
                root.set("transcripts", new_transcripts)

            # Add a new <transcript> tag inside <transcripts> for the
            # target language, inheriting attributes
            for video_asset in root.findall("video_asset"):
                for transcripts in video_asset.findall("transcripts"):
                    existing_transcript = transcripts.find("transcript")
                    new_transcript = Element("transcript")
                    if existing_transcript is not None:
                        new_transcript.attrib = existing_transcript.attrib.copy()
                    new_transcript.set("language_code", lang_code)
                    # Avoid duplicates
                    if not any(
                        t.attrib == new_transcript.attrib
                        for t in transcripts.findall("transcript")
                    ):
                        transcripts.append(new_transcript)

            # Add a new <transcript> tag for the target language
            for transcript in root.findall("transcript"):
                src = transcript.get("src")
                if src:
                    new_src = re.sub(r"-[a-zA-Z]{2}\.srt$", f"-{lang_code}.srt", src)
                    new_transcript = Element("transcript")
                    new_transcript.set("language", lang_code)
                    new_transcript.set("src", new_src)
                    # Avoid duplicates
                    if not any(
                        t.get("language") == lang_code and t.get("src") == new_src
                        for t in root.findall("transcript")
                    ):
                        root.append(new_transcript)

            xml_content = ElementTree.tostring(root, encoding="unicode")
        except Exception as e:  # noqa: BLE001
            logger.warning("Failed to update transcripts in video XML: %s", e)

        return xml_content

    def _translate_file(
        self, file_path: Path, source_language: str, translation_language: str
    ) -> int:
        """Translate a single file and return billed characters."""
        # Handle SRT files with DeepL document translation
        if file_path.suffix == ".srt":
            try:
                billed_chars = self.translate_srt_file(
                    file_path, source_language, translation_language
                )
            except Exception as e:  # noqa: BLE001
                logger.warning("Failed to translate SRT %s: %s", file_path, e)
                return 0
            else:
                return billed_chars

        try:
            content = file_path.read_text(encoding="utf-8")
            logger.debug("Translating: %s", file_path)

            translated_content, billed_chars = self._translate_text(
                content, source_language, translation_language, file_path.name
            )

            # Handle XML display_name translation
            if file_path.suffix == ".xml":
                translated_content = self._translate_display_name(
                    translated_content, source_language, translation_language
                )

                # If parent directory is 'video', update transcripts attribute
                if file_path.parent.name == "video":
                    translated_content = self._update_video_xml(
                        translated_content, translation_language
                    )

            file_path.write_text(translated_content, encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            logger.warning("Failed to translate %s: %s", file_path, e)
            return 0
        else:
            return billed_chars

    def _translate_grading_policy(
        self, course_dir: Path, source_language: str, translation_language: str
    ) -> int:
        """Translate grading_policy.json files."""
        total_billed_chars = 0
        policies_dir = course_dir / "course" / "policies"

        if not policies_dir.exists():
            return 0

        for child_dir in policies_dir.iterdir():
            if not child_dir.is_dir():
                continue

            grading_policy_path = child_dir / "grading_policy.json"
            if not grading_policy_path.exists():
                continue

            try:
                grading_policy = json.loads(
                    grading_policy_path.read_text(encoding="utf-8")
                )
                updated = False

                for item in grading_policy.get("GRADER", []):
                    if "short_label" in item:
                        translated_label, billed_chars = self._translate_text(
                            item["short_label"], source_language, translation_language
                        )
                        item["short_label"] = translated_label
                        total_billed_chars += billed_chars
                        updated = True

                if updated:
                    grading_policy_path.write_text(
                        json.dumps(grading_policy, ensure_ascii=False, indent=4),
                        encoding="utf-8",
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning(
                    "Failed to translate grading policy in %s: %s", child_dir, e
                )

        return total_billed_chars

    def _translate_policy_json(
        self, course_dir: Path, source_language: str, translation_language: str
    ) -> int:
        """Translate policy.json files."""
        total_billed_chars = 0
        policies_dir = course_dir / "course" / "policies"

        if not policies_dir.exists():
            return 0

        for child_dir in policies_dir.iterdir():
            if not child_dir.is_dir():
                continue

            policy_path = child_dir / "policy.json"
            if not policy_path.exists():
                continue

            try:
                policy_data = json.loads(policy_path.read_text(encoding="utf-8"))
                updated = False

                for course_obj in policy_data.values():
                    if not isinstance(course_obj, dict):
                        continue

                    # Translate various fields
                    billed_chars, field_updated = self._translate_policy_fields(
                        course_obj, source_language, translation_language
                    )
                    total_billed_chars += billed_chars
                    updated = updated or field_updated

                if updated:
                    policy_path.write_text(
                        json.dumps(policy_data, ensure_ascii=False, indent=4),
                        encoding="utf-8",
                    )
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Failed to translate policy in %s: %s", child_dir, e)

        return total_billed_chars

    def _translate_policy_fields(
        self,
        course_obj: dict[str, Any],
        source_language: str,
        translation_language: str,
    ) -> tuple[int, bool]:
        """Translate specific fields in policy object."""
        total_billed_chars = 0
        updated = False

        # Translate simple string fields
        billed_chars, field_updated = self._translate_string_fields(
            course_obj, source_language, translation_language
        )
        total_billed_chars += billed_chars
        updated = updated or field_updated

        # Translate discussion topics
        billed_chars, field_updated = self._translate_discussion_topics(
            course_obj, source_language, translation_language
        )
        total_billed_chars += billed_chars
        updated = updated or field_updated

        # Translate learning info and tabs
        billed_chars, field_updated = self._translate_learning_info_and_tabs(
            course_obj, source_language, translation_language
        )
        total_billed_chars += billed_chars
        updated = updated or field_updated

        # Translate XML attributes
        billed_chars, field_updated = self._translate_xml_attributes(
            course_obj, source_language, translation_language
        )
        total_billed_chars += billed_chars
        updated = updated or field_updated

        return total_billed_chars, updated

    def _translate_string_fields(
        self,
        course_obj: dict[str, Any],
        source_language: str,
        translation_language: str,
    ) -> tuple[int, bool]:
        """Translate simple string fields."""
        total_billed_chars = 0
        updated = False

        string_fields = ["advertised_start", "display_name", "display_organization"]
        for field in string_fields:
            if field in course_obj:
                translated, billed_chars = self._translate_text(
                    course_obj[field], source_language, translation_language
                )
                course_obj[field] = translated
                total_billed_chars += billed_chars
                updated = True

        return total_billed_chars, updated

    def _translate_discussion_topics(
        self,
        course_obj: dict[str, Any],
        source_language: str,
        translation_language: str,
    ) -> tuple[int, bool]:
        """Translate discussion topics."""
        total_billed_chars = 0
        updated = False

        if "discussion_topics" in course_obj:
            topics = course_obj["discussion_topics"]
            if isinstance(topics, dict):
                new_topics = {}
                for topic_key, value in topics.items():
                    translated_key, billed_chars = self._translate_text(
                        topic_key, source_language, translation_language
                    )
                    new_topics[translated_key] = value
                    total_billed_chars += billed_chars
                course_obj["discussion_topics"] = new_topics
                updated = True

        return total_billed_chars, updated

    def _translate_learning_info_and_tabs(
        self,
        course_obj: dict[str, Any],
        source_language: str,
        translation_language: str,
    ) -> tuple[int, bool]:
        """Translate learning info and tabs."""
        total_billed_chars = 0
        updated = False

        # Learning info
        if "learning_info" in course_obj and isinstance(
            course_obj["learning_info"], list
        ):
            translated_info = []
            for item in course_obj["learning_info"]:
                translated, billed_chars = self._translate_text(
                    item, source_language, translation_language
                )
                translated_info.append(translated)
                total_billed_chars += billed_chars
            course_obj["learning_info"] = translated_info
            updated = True

        # Tabs
        if "tabs" in course_obj and isinstance(course_obj["tabs"], list):
            for tab in course_obj["tabs"]:
                if isinstance(tab, dict) and "name" in tab:
                    translated, billed_chars = self._translate_text(
                        tab["name"], source_language, translation_language
                    )
                    tab["name"] = translated
                    total_billed_chars += billed_chars
                    updated = True

        return total_billed_chars, updated

    def _translate_xml_attributes(
        self,
        course_obj: dict[str, Any],
        source_language: str,
        translation_language: str,
    ) -> tuple[int, bool]:
        """Translate XML attributes."""
        total_billed_chars = 0
        updated = False

        if "xml_attributes" in course_obj and isinstance(
            course_obj["xml_attributes"], dict
        ):
            xml_attrs = course_obj["xml_attributes"]
            xml_fields = [
                "diplay_name",
                "info_sidebar_name",
            ]  # Note: keeping typo as in original
            for field in xml_fields:
                if field in xml_attrs:
                    translated, billed_chars = self._translate_text(
                        xml_attrs[field], source_language, translation_language
                    )
                    xml_attrs[field] = translated
                    total_billed_chars += billed_chars
                    updated = True

        return total_billed_chars, updated

    def _create_translated_archive(
        self, translated_dir: Path, translation_language: str, original_name: str
    ) -> Path:
        """Create tar.gz archive of translated course."""
        # Remove all archive extensions from the original name
        ext = self.get_supported_archive_extension(original_name)
        clean_name = original_name[: -len(ext)] if ext else original_name

        tar_gz_name = f"{translation_language}_{clean_name}.tar.gz"
        tar_gz_path = translated_dir.parent / tar_gz_name

        # Remove existing archive
        if tar_gz_path.exists():
            tar_gz_path.unlink()

        # Create tar.gz archive containing only the 'course' directory
        course_dir_path = translated_dir / "course"
        with tarfile.open(tar_gz_path, "w:gz") as tar:
            tar.add(course_dir_path, arcname="course")

        # Delete extracted directory after copying
        if translated_dir.exists():
            shutil.rmtree(translated_dir)

        logger.info("Created tar.gz archive: %s", tar_gz_path)
        return tar_gz_path

    def translate_srt_file(
        self, input_file_path: Path, source_language: str, target_language: str
    ) -> int:
        """
        Translate an SRT file using DeepL document translation.
        Creates a new output file with the target language prefix, then renames
        it to the original file. Returns the number of billed characters.
        """
        input_name = input_file_path.name
        output_name = input_name
        if "-" in input_name and input_name.endswith(".srt"):
            parts = input_name.rsplit("-", 1)
            output_name = f"{parts[0]}-{target_language.lower()}.srt"
        output_file_path = input_file_path.parent / output_name

        deepl_client = deepl.Translator(settings.DEEPL_API_KEY)
        result = deepl_client.translate_document_from_filepath(
            input_file_path,
            output_file_path,
            source_lang=source_language,
            target_lang=target_language,
        )
        return result.billed_characters

    def _translate_text(
        self,
        text: str,
        source_language: str,
        target_language: str,
        filename: str | None = None,
    ) -> tuple[str, int]:
        """Translate text using DeepL API."""
        if not text or not text.strip():
            return text, 0

        try:
            deepl_client = deepl.Translator(settings.DEEPL_API_KEY)

            tag_handling = None
            if filename:
                extension = Path(filename).suffix.lstrip(".")
                if extension in ["html", "xml"]:
                    tag_handling = extension

            result = deepl_client.translate_text(
                text,
                source_lang=source_language,
                target_lang=target_language,
                tag_handling=tag_handling,
            )

            return result.text, result.billed_characters  # noqa: TRY300
        except (deepl.exceptions.DeepLException, OSError) as e:
            logger.warning("Translation failed for text: %s... Error: %s", text[:50], e)
            return text, 0

    def _translate_display_name(
        self, xml_content: str, source_language: str, target_language: str
    ) -> str:
        """Extract and translate the display_name attribute of the root element."""
        try:
            root = ElementTree.fromstring(xml_content)
            display_name = root.attrib.get("display_name")

            if display_name:
                translated_name, _ = self._translate_text(
                    display_name, source_language, target_language
                )
                root.set("display_name", translated_name)
                return ElementTree.tostring(root, encoding="unicode")
        except ElementTree.ParseError as e:
            logger.warning("Could not translate display_name: %s", e)

        return xml_content
