"""
Management command to translate course content to a specified language.
"""
import logging
import deepl
import os
import tarfile
import shutil
import xml.etree.ElementTree as ET
import json

from django.core.management.base import BaseCommand

log = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Translate given course content to the specified language.
    """
    help = (
        "Translate course content to the specified language."
    )

    def add_arguments(self, parser):
        """
        Entry point for subclassed commands to add custom arguments.
        """
        parser.add_argument(
            '--source-language',
            dest='source_language',
            default='EN',
            help='Specify the source language of the course content.'
        )
        parser.add_argument(
            '--translation-language',
            dest='translation_language',
            help='Specify the language to translate the course content into.'
        )
        parser.add_argument(
            '--course-dir',
            dest='course_directory',
            help='Specify the course directory.'
        )

    def handle(self, *args, **options):
        course_dir = options.get('course_directory')
        source_language = options.get('source_language')
        translation_language = options.get('translation_language')
        extract_dir = '/openedx/course_translations'
        target_dirs = ['about', 'course', 'chapter', 'html', 'info', 'problem', 'sequential', 'vertical', 'video']

        # Only support tar files
        if not (course_dir.endswith('.tar.gz') or course_dir.endswith('.tgz') or course_dir.endswith('.tar')):
            raise ValueError("course-dir must be a tar file (.tar.gz, .tgz, .tar)")

        if not os.path.exists(extract_dir):
            os.makedirs(extract_dir)
        tarball_base = os.path.basename(course_dir)
        for ext in ['.tar.gz', '.tgz', '.tar']:
            if tarball_base.endswith(ext):
                tarball_base = tarball_base[:-len(ext)]
                break
        extracted_course_dir = os.path.join(extract_dir, tarball_base)
        if not os.path.exists(extracted_course_dir):
            with tarfile.open(course_dir, 'r:*') as tar:
                tar.extractall(path=extracted_course_dir)
        source_dir = extracted_course_dir

        # Step 2: Always copy to /openedx/course_translations/{translation_language}_{base_name}
        base_name = os.path.basename(source_dir)
        new_dir_name = f"{translation_language}_{base_name}"
        new_dir_path = os.path.join(extract_dir, new_dir_name)
        if os.path.exists(new_dir_path):
            shutil.rmtree(new_dir_path)
        shutil.copytree(source_dir, new_dir_path)
        print(f"Copied {source_dir} to {new_dir_path}")

        # Step 3: Traverse copied directory (including its parent) and print html/xml files
        billed_char_count = 0
        parent_dir = os.path.dirname(new_dir_path)
        for search_dir in [new_dir_path, parent_dir]:
            for file in os.listdir(search_dir):
                file_path = os.path.join(search_dir, file)
                if os.path.isfile(file_path) and (file.endswith('.html') or file.endswith('.xml')):
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        print(f"--- Contents of {file_path} ---")
                        translated_content, billed_chars = self._translate_text(
                            content,
                            source_language,
                            translation_language,
                            file,
                        )
                        billed_char_count = billed_char_count + billed_chars

                        # If XML, translate display_name attribute
                        if file.endswith('.xml'):
                            translated_content = translate_display_name(
                                translated_content,
                                source_language,
                                translation_language,
                                self._translate_text
                            )

                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(translated_content)

            for dir_name in target_dirs:
                dir_path = os.path.join(search_dir, dir_name)
                if os.path.exists(dir_path) and os.path.isdir(dir_path):
                    for root, _, files in os.walk(dir_path):
                        for file in files:
                            if file.endswith('.html') or file.endswith('.xml'):
                                file_path = os.path.join(root, file)
                                with open(file_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                    print(f"--- Contents of {file_path} ---")
                                    translated_content, billed_chars = self._translate_text(
                                        content,
                                        source_language,
                                        translation_language,
                                        file,
                                    )
                                    billed_char_count = billed_char_count + billed_chars

                                    # If XML, translate display_name attribute
                                    if file.endswith('.xml'):
                                        translated_content = translate_display_name(
                                            translated_content,
                                            source_language,
                                            translation_language,
                                            self._translate_text
                                        )

                                with open(file_path, 'w', encoding='utf-8') as f:
                                    f.write(translated_content)

        # Step 3.1: Translate grading_policy.json short_label fields
        policies_dir = os.path.join(new_dir_path, "course", "policies")
        if os.path.exists(policies_dir):
            for child in os.listdir(policies_dir):
                child_dir = os.path.join(policies_dir, child)
                grading_policy_path = os.path.join(child_dir, "grading_policy.json")
                if os.path.isfile(grading_policy_path):
                    with open(grading_policy_path, "r", encoding="utf-8") as f:
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
                        with open(grading_policy_path, "w", encoding="utf-8") as f:
                            json.dump(grading_policy, f, ensure_ascii=False, indent=4)

        # Step 3.2: Translate specified fields in policy.json
        policies_dir = os.path.join(new_dir_path, "course", "policies")
        if os.path.exists(policies_dir):
            for child in os.listdir(policies_dir):
                child_dir = os.path.join(policies_dir, child)
                policy_json_path = os.path.join(child_dir, "policy.json")
                if os.path.isfile(policy_json_path):
                    with open(policy_json_path, "r", encoding="utf-8") as f:
                        policy_data = json.load(f)
                    updated = False
                    for course_key, course_obj in policy_data.items():
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
                        if "learning_info" in course_obj and isinstance(course_obj["learning_info"], list):
                            course_obj["learning_info"] = [
                                self._translate_text(item, source_language, translation_language)[0]
                                for item in course_obj["learning_info"]
                            ]
                            updated = True
                        # 6. tabs: translate name of each tab
                        if "tabs" in course_obj and isinstance(course_obj["tabs"], list):
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
                        if "xml_attributes" in course_obj and isinstance(course_obj["xml_attributes"], dict):
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
                        with open(policy_json_path, "w", encoding="utf-8") as f:
                            json.dump(policy_data, f, ensure_ascii=False, indent=4)

        # Step 4: Create .zip archive of the translated 'course' directory only
        zip_name = f"{translation_language}_{tarball_base}.zip"
        zip_path = os.path.join(extract_dir, zip_name)

        # Remove existing archive if it exists
        if os.path.exists(zip_path):
            os.remove(zip_path)

        # Create .zip archive containing only the 'course' directory
        shutil.make_archive(
            base_name=os.path.join(extract_dir, f"{translation_language}_{tarball_base}"),
            format='zip',
            root_dir=new_dir_path,
            base_dir="course"
        )
        print(f"Created zip archive: {zip_path}")
        print(billed_char_count)

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
            tag_handling=file.split('.')[-1] if file else None,
            # tag_handling_version='v2',
        )
        return result.text, result.billed_characters

def translate_display_name(xml_content, source_language, target_language, translate_func):
    """
    Extracts and translates the display_name attribute of the root element in the XML content.
    Returns the updated XML string.
    """
    try:
        root = ET.fromstring(xml_content)
        display_name = root.attrib.get("display_name")
        if display_name:
            translated_name, _ = translate_func(
                display_name,
                source_language,
                target_language
            )
            root.set("display_name", translated_name)
            # Return the updated XML as string
            return ET.tostring(root, encoding="unicode")
    except Exception as e:
        log.warning(f"Could not translate display_name: {e}")
    return xml_content

