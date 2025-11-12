"""
Management command to translate course content to a specified language.
"""

import json
import logging
import os
import shutil
import tarfile
import xml.etree.ElementTree as ET

import deepl
from django.conf import settings
from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Translate given course content to the specified language.
    """

    help = "Translate course content to the specified language."

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            "--source-language",
            dest="source_language",
            default="EN",
            help="Specify the source language of the course content.",
        )
        parser.add_argument(
            "--translation-language",
            dest="translation_language",
            help="Specify the language to translate the course content into.",
        )
        parser.add_argument(
            "--course-dir",
            dest="course_directory",
            help="Specify the course directory.",
        )

    def handle(self, *args, **options):  # noqa: C901, PLR0912, PLR0915, ARG002
        course_dir = options.get("course_directory")
        source_language = options.get("source_language")
        translation_language = options.get("translation_language")
        extract_dir = "/openedx/course_translations"
        target_dirs = [
            "about",
            "course",
            "chapter",
            "html",
            "info",
            "problem",
            "sequential",
            "vertical",
            "video",
        ]

        # Only support tar files
        if not (
            course_dir.endswith(".tar.gz")  # noqa: PIE810
            or course_dir.endswith(".tgz")
            or course_dir.endswith(".tar")
        ):
            raise ValueError("course-dir must be a tar file (.tar.gz, .tgz, .tar)")  # noqa: TRY003, EM101

        if not os.path.exists(extract_dir):  # noqa: PTH110
            os.makedirs(extract_dir)  # noqa: PTH103
        tarball_base = os.path.basename(course_dir)  # noqa: PTH119
        for ext in [".tar.gz", ".tgz", ".tar"]:
            if tarball_base.endswith(ext):
                tarball_base = tarball_base[: -len(ext)]
                break
        extracted_course_dir = os.path.join(extract_dir, tarball_base)  # noqa: PTH118
        if not os.path.exists(extracted_course_dir):  # noqa: PTH110
            with tarfile.open(course_dir, "r:*") as tar:
                tar.extractall(path=extracted_course_dir)  # noqa: S202
        source_dir = extracted_course_dir

        # Step 2: Always copy to /openedx/course_translations/{translation_language}_{base_name}  # noqa: E501
        base_name = os.path.basename(source_dir)  # noqa: PTH119
        new_dir_name = f"{translation_language}_{base_name}"
        new_dir_path = os.path.join(extract_dir, new_dir_name)  # noqa: PTH118
        if os.path.exists(new_dir_path):  # noqa: PTH110
            shutil.rmtree(new_dir_path)
        shutil.copytree(source_dir, new_dir_path)
        log.info(f"Copied {source_dir} to {new_dir_path}")  # noqa: G004

        # Step 3: Traverse copied directory (including its parent)
        billed_char_count = 0
        parent_dir = os.path.dirname(new_dir_path)  # noqa: PTH120
        for search_dir in [new_dir_path, parent_dir]:
            for file in os.listdir(search_dir):  # noqa: PTH208
                file_path = os.path.join(search_dir, file)  # noqa: PTH118
                if os.path.isfile(file_path) and (  # noqa: PTH113
                    file.endswith(".html") or file.endswith(".xml")  # noqa: PIE810
                ):
                    with open(file_path, encoding="utf-8") as f:  # noqa: PTH123
                        content = f.read()
                        log.info(f"--- Contents of {file_path} ---")  # noqa: G004
                        translated_content, billed_chars = self._translate_text(
                            content,
                            source_language,
                            translation_language,
                            file,
                        )
                        billed_char_count = billed_char_count + billed_chars

                        # If XML, translate display_name attribute
                        if file.endswith(".xml"):
                            translated_content = translate_display_name(
                                translated_content,
                                source_language,
                                translation_language,
                                self._translate_text,
                            )

                    with open(file_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                        f.write(translated_content)

            for dir_name in target_dirs:
                dir_path = os.path.join(search_dir, dir_name)  # noqa: PTH118
                if os.path.exists(dir_path) and os.path.isdir(dir_path):  # noqa: PTH110, PTH112
                    for root, _, files in os.walk(dir_path):
                        for file in files:
                            if file.endswith(".html") or file.endswith(".xml"):  # noqa: PIE810
                                file_path = os.path.join(root, file)  # noqa: PTH118
                                with open(file_path, encoding="utf-8") as f:  # noqa: PTH123
                                    content = f.read()
                                    log.info(f"--- Contents of {file_path} ---")  # noqa: G004
                                    translated_content, billed_chars = (
                                        self._translate_text(
                                            content,
                                            source_language,
                                            translation_language,
                                            file,
                                        )
                                    )
                                    billed_char_count = billed_char_count + billed_chars

                                    # If XML, translate display_name attribute
                                    if file.endswith(".xml"):
                                        translated_content = translate_display_name(
                                            translated_content,
                                            source_language,
                                            translation_language,
                                            self._translate_text,
                                        )

                                with open(file_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                                    f.write(translated_content)

        # Step 3.1: Translate grading_policy.json short_label fields
        policies_dir = os.path.join(new_dir_path, "course", "policies")  # noqa: PTH118
        if os.path.exists(policies_dir):  # noqa: PTH110
            for child in os.listdir(policies_dir):  # noqa: PTH208
                child_dir = os.path.join(policies_dir, child)  # noqa: PTH118
                grading_policy_path = os.path.join(child_dir, "grading_policy.json")  # noqa: PTH118
                if os.path.isfile(grading_policy_path):  # noqa: PTH113
                    with open(grading_policy_path, encoding="utf-8") as f:  # noqa: PTH123
                        grading_policy = json.load(f)
                    updated = False
                    for item in grading_policy.get("GRADER", []):
                        if "short_label" in item:
                            translated_label, _ = self._translate_text(
                                item["short_label"],
                                source_language,
                                translation_language,
                            )
                            item["short_label"] = translated_label
                            updated = True
                    if updated:
                        with open(grading_policy_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                            json.dump(grading_policy, f, ensure_ascii=False, indent=4)

        # Step 3.2: Translate specified fields in policy.json
        policies_dir = os.path.join(new_dir_path, "course", "policies")  # noqa: PTH118
        if os.path.exists(policies_dir):  # noqa: PTH110
            for child in os.listdir(policies_dir):  # noqa: PTH208
                child_dir = os.path.join(policies_dir, child)  # noqa: PTH118
                policy_json_path = os.path.join(child_dir, "policy.json")  # noqa: PTH118
                if os.path.isfile(policy_json_path):  # noqa: PTH113
                    with open(policy_json_path, encoding="utf-8") as f:  # noqa: PTH123
                        policy_data = json.load(f)
                    updated = False
                    for course_key, course_obj in policy_data.items():  # noqa: B007, PERF102
                        # 1. advertised_start
                        if "advertised_start" in course_obj:
                            translated, _ = self._translate_text(
                                course_obj["advertised_start"],
                                source_language,
                                translation_language,
                            )
                            course_obj["advertised_start"] = translated
                            updated = True
                        # 2. all keys against discussion_topics
                        if "discussion_topics" in course_obj:
                            topic_keys = list(course_obj["discussion_topics"].keys())
                            for topic_key in topic_keys:
                                translated, _ = self._translate_text(
                                    topic_key,
                                    source_language,
                                    translation_language,
                                )
                                # Replace key with translated key
                                value = course_obj["discussion_topics"].pop(topic_key)
                                course_obj["discussion_topics"][translated] = value
                                updated = True
                        # 3. display_name
                        if "display_name" in course_obj:
                            translated, _ = self._translate_text(
                                course_obj["display_name"],
                                source_language,
                                translation_language,
                            )
                            course_obj["display_name"] = translated
                            updated = True
                        # 4. display_organization
                        if "display_organization" in course_obj:
                            translated, _ = self._translate_text(
                                course_obj["display_organization"],
                                source_language,
                                translation_language,
                            )
                            course_obj["display_organization"] = translated
                            updated = True
                        # 5. learning_info (list)
                        if "learning_info" in course_obj and isinstance(
                            course_obj["learning_info"], list
                        ):
                            course_obj["learning_info"] = [
                                self._translate_text(
                                    item, source_language, translation_language
                                )[0]
                                for item in course_obj["learning_info"]
                            ]
                            updated = True
                        # 6. tabs: translate name of each tab
                        if "tabs" in course_obj and isinstance(
                            course_obj["tabs"], list
                        ):
                            for tab in course_obj["tabs"]:
                                if "name" in tab:
                                    translated, _ = self._translate_text(
                                        tab["name"],
                                        source_language,
                                        translation_language,
                                    )
                                    tab["name"] = translated
                                    updated = True
                        # 7. xml_attributes: diplay_name and info_sidebar_name
                        if "xml_attributes" in course_obj and isinstance(
                            course_obj["xml_attributes"], dict
                        ):
                            xml_attrs = course_obj["xml_attributes"]
                            if "diplay_name" in xml_attrs:
                                translated, _ = self._translate_text(
                                    xml_attrs["diplay_name"],
                                    source_language,
                                    translation_language,
                                )
                                xml_attrs["diplay_name"] = translated
                                updated = True
                            if "info_sidebar_name" in xml_attrs:
                                translated, _ = self._translate_text(
                                    xml_attrs["info_sidebar_name"],
                                    source_language,
                                    translation_language,
                                )
                                xml_attrs["info_sidebar_name"] = translated
                                updated = True
                    if updated:
                        with open(policy_json_path, "w", encoding="utf-8") as f:  # noqa: PTH123
                            json.dump(policy_data, f, ensure_ascii=False, indent=4)

        # Step 4: Create .zip archive of the translated 'course' directory only
        zip_name = f"{translation_language}_{tarball_base}.zip"
        zip_path = os.path.join(extract_dir, zip_name)  # noqa: PTH118

        # Remove existing archive if it exists
        if os.path.exists(zip_path):  # noqa: PTH110
            os.remove(zip_path)  # noqa: PTH107

        # Create .zip archive containing only the 'course' directory
        shutil.make_archive(
            base_name=os.path.join(  # noqa: PTH118
                extract_dir,
                f"{translation_language}_{tarball_base}",
            ),
            format="zip",
            root_dir=new_dir_path,
            base_dir="course",
        )
        log.info(f"Created zip archive: {zip_path}")  # noqa: G004
        log.info(billed_char_count)

    def _translate_text(self, text, source_language, target_language, file=None):
        """
        Translate the given text to the target language using DeepL API.
        """
        auth_key = settings.DEEPL_API_KEY
        deepl_client = deepl.DeepLClient(auth_key)
        result = deepl_client.translate_text(
            text,
            source_lang=source_language,
            target_lang=target_language,
            tag_handling=file.split(".")[-1] if file else None,
            # tag_handling_version='v2',  # noqa: ERA001
        )
        return result.text, result.billed_characters


def translate_display_name(
    xml_content, source_language, target_language, translate_func
):
    """
    Extract and translate the display_name attribute
    of the root element in the XML content.

    Returns the updated XML string.
    """
    try:
        # TODO: Using `xml` to parse untrusted data is  # noqa: FIX002, TD003, TD002
        #  known to be vulnerable to XML attacks; use `defusedxml` equivalents
        root = ET.fromstring(xml_content)  # noqa: S314
        display_name = root.attrib.get("display_name")
        if display_name:
            translated_name, _ = translate_func(
                display_name, source_language, target_language
            )
            root.set("display_name", translated_name)
            # Return the updated XML as string
            return ET.tostring(root, encoding="unicode")
    except Exception as e:  # noqa: BLE001
        log.warning(f"Could not translate display_name: {e}")  # noqa: G004
    return xml_content
