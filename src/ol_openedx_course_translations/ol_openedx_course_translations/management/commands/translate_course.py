"""
Management command to translate course content to a specified language.
"""

import logging
import shutil
from pathlib import Path

from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ol_openedx_course_translations.tasks import (
    translate_file_task,
    translate_grading_policy_task,
    translate_policy_json_task,
)
from ol_openedx_course_translations.utils.course_translations import (
    create_translated_archive,
    create_translated_copy,
    extract_course_archive,
    get_translatable_file_paths,
    update_course_language_attribute,
    validate_course_inputs,
    validate_translation_provider,
)

logger = logging.getLogger(__name__)

# Task configuration
TASK_TIMEOUT_SECONDS = 3600  # 1 hour total timeout for all tasks
TASK_POLL_INTERVAL_SECONDS = 2  # Poll every 2 seconds for task completion


class Command(BaseCommand):
    """Translate given course content to the specified language."""

    help = "Translate course content to the specified language."

    def __init__(self, *args, **kwargs):
        """Initialize the command with empty task list."""
        super().__init__(*args, **kwargs)
        self.tasks = []

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
            "--target-language",
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
            "--content-translation-provider",
            dest="content_translation_provider",
            required=True,
            help=(
                "Translation provider for content (XML/HTML and text). "
                "Format: 'deepl' or 'PROVIDER/MODEL' "
                "(e.g., 'openai/gpt-5.2', 'gemini/gemini-3-pro-preview')"
            ),
        )
        parser.add_argument(
            "--srt-translation-provider",
            dest="srt_translation_provider",
            required=True,
            help=(
                "Translation provider for SRT subtitles. "
                "Format: 'deepl' or 'PROVIDER/MODEL' "
                "(e.g., 'openai/gpt-5.2', 'gemini/gemini-3-pro-preview')"
            ),
        )
        parser.add_argument(
            "--glossary-dir",
            dest="glossary_directory",
            required=False,
            help=(
                "Path to glossary directory containing "
                "language-specific glossary files."
            ),
        )

    def _parse_provider_spec(self, provider_spec: str) -> tuple[str, str | None]:
        """
        Parse provider specification into provider name and model.

        Args:
            provider_spec: Provider specification (e.g., 'deepl', 'openai/gpt-5.2')

        Returns:
            Tuple of (provider_name, model_name)
        """
        if "/" in provider_spec:
            parts = provider_spec.split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:  # noqa: PLR2004
                error_msg = (
                    f"Invalid provider specification: {provider_spec}. "
                    "Use format 'PROVIDER/MODEL' (e.g., 'openai/gpt-5.2')"
                )
                raise CommandError(error_msg)
            return parts[0].lower(), parts[1]
        else:
            # For deepl, no model is needed
            return provider_spec.lower(), None

    def handle(self, **options) -> None:
        """Handle the translate_course command."""
        try:
            course_archive_path = Path(options["course_archive_path"])
            source_language = options["source_language"]
            target_language = options["target_language"]
            content_provider_spec = options["content_translation_provider"]
            srt_provider_spec = options["srt_translation_provider"]
            glossary_directory = options.get("glossary_directory")

            # Parse provider specifications
            content_provider_name, content_model = self._parse_provider_spec(
                content_provider_spec
            )
            srt_provider_name, srt_model = self._parse_provider_spec(srt_provider_spec)

            # Validate inputs
            validate_course_inputs(course_archive_path)

            # Validate providers before proceeding
            try:
                validate_translation_provider(content_provider_name, content_model)
                validate_translation_provider(srt_provider_name, srt_model)
            except ValueError as e:
                raise CommandError(str(e)) from e

            # Store provider names and models
            self.content_provider_name = content_provider_name
            self.content_model = content_model
            self.srt_provider_name = srt_provider_name
            self.srt_model = srt_model
            self.glossary_directory = glossary_directory

            # Extract course archive
            extracted_course_dir = extract_course_archive(course_archive_path)

            # Create translated copy
            translated_course_dir = create_translated_copy(
                extracted_course_dir, target_language
            )

            # Delete extracted directory after copying
            if extracted_course_dir.exists():
                shutil.rmtree(extracted_course_dir)

            # Translate content asynchronously
            self._translate_course_content_async(
                translated_course_dir, source_language, target_language
            )

            # Wait for all tasks and report status
            self._wait_and_report_tasks()

            # Create final archive
            translated_archive_path = create_translated_archive(
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

    def _translate_course_content_async(
        self, course_dir: Path, source_language: str, target_language: str
    ) -> None:
        """
        Translate all course content using Celery tasks.

        Args:
            course_dir: Path to the course directory
            source_language: Source language code
            target_language: Target language code

        Raises:
            CommandError: If course directory is not found
        """
        course_directory = course_dir / "course"

        if not course_directory.exists() or not course_directory.is_dir():
            error_msg = f"Course directory not found: {course_directory}"
            raise CommandError(error_msg)

        # Update language attributes in course XML, doing this
        # because tasks can override the XML files
        update_course_language_attribute(course_directory, target_language)

        # Collect all tasks
        self.tasks = []

        # Add translation tasks for files in course directory
        self._add_file_translation_tasks(
            course_directory, source_language, target_language, recursive=False
        )

        # Add translation tasks for target subdirectories
        for target_dir_name in settings.COURSE_TRANSLATIONS_TARGET_DIRECTORIES:
            target_directory = course_directory / target_dir_name
            if target_directory.exists() and target_directory.is_dir():
                self._add_file_translation_tasks(
                    target_directory, source_language, target_language, recursive=True
                )

        # Add tasks for special JSON files
        self._add_grading_policy_tasks(course_dir, target_language)
        self._add_policy_json_tasks(course_dir, target_language)

    def _add_file_translation_tasks(
        self,
        directory_path: Path,
        source_language: str,
        target_language: str,
        *,
        recursive: bool = False,
    ) -> None:
        """
        Add Celery tasks for file translation to the task list.

        Args:
            directory_path: Path to directory containing files to translate
            source_language: Source language code
            target_language: Target language code
            recursive: Whether to search for files recursively
        """
        translatable_file_paths = get_translatable_file_paths(
            directory_path, recursive=recursive
        )

        for file_path in translatable_file_paths:
            task = translate_file_task.s(
                str(file_path),
                source_language,
                target_language,
                self.content_provider_name,
                self.content_model,
                self.srt_provider_name,
                self.srt_model,
                self.glossary_directory,
            )
            self.tasks.append(("file", str(file_path), task))
            logger.info("Added translation task for: %s", file_path)

    def _add_grading_policy_tasks(self, course_dir: Path, target_language: str) -> None:
        """
        Add Celery tasks for grading_policy.json translation to the task list.

        Args:
            course_dir: Path to the course directory
            target_language: Target language code
        """
        course_policies_dir = course_dir / "course" / "policies"

        if not course_policies_dir.exists():
            return

        for policy_child_dir in course_policies_dir.iterdir():
            if not policy_child_dir.is_dir():
                continue

            grading_policy_file = policy_child_dir / "grading_policy.json"
            if grading_policy_file.exists():
                task = translate_grading_policy_task.s(
                    str(grading_policy_file),
                    target_language,
                    self.content_provider_name,
                    self.content_model,
                    self.glossary_directory,
                )
                self.tasks.append(("grading_policy", str(grading_policy_file), task))
                logger.info("Added grading policy task for: %s", grading_policy_file)

    def _add_policy_json_tasks(self, course_dir: Path, target_language: str) -> None:
        """
        Add Celery tasks for policy.json translation to the task list.

        Args:
            course_dir: Path to the course directory
            target_language: Target language code
        """
        course_policies_dir = course_dir / "course" / "policies"

        if not course_policies_dir.exists():
            return

        for policy_child_dir in course_policies_dir.iterdir():
            if not policy_child_dir.is_dir():
                continue

            policy_file = policy_child_dir / "policy.json"
            if policy_file.exists():
                task = translate_policy_json_task.s(
                    str(policy_file),
                    target_language,
                    self.content_provider_name,
                    self.content_model,
                    self.glossary_directory,
                )
                self.tasks.append(("policy", str(policy_file), task))
                logger.info("Added policy.json task for: %s", policy_file)

    def _wait_and_report_tasks(self) -> None:  # noqa: C901
        """
        Execute all tasks as a Celery group and wait for completion.

        Uses Celery's group primitive to execute tasks in parallel and
        provides detailed status reporting.

        Raises:
            CommandError: If any tasks fail
        """
        if not self.tasks:
            self.stdout.write("No tasks to execute.")
            return

        total_tasks = len(self.tasks)
        self.stdout.write(
            f"\nExecuting {total_tasks} translation tasks in parallel...\n"
        )

        # Extract task signatures and create mappings
        task_signatures = [task_sig for _, _, task_sig in self.tasks]
        task_metadata = {
            i: (task_type, file_path)
            for i, (task_type, file_path, _) in enumerate(self.tasks)
        }

        # Create and execute group
        job = group(task_signatures)
        result = job.apply_async()

        # Wait for all tasks to complete with timeout
        try:
            results = result.get(
                timeout=TASK_TIMEOUT_SECONDS,
                interval=TASK_POLL_INTERVAL_SECONDS,
                propagate=False,
            )
        except Exception as e:
            logger.exception("Task execution failed")
            error_msg = f"Task execution timeout or error: {e}"
            raise CommandError(error_msg) from e

        # Process results
        completed_tasks = 0
        failed_tasks = 0
        skipped_tasks = 0

        for i, task_result in enumerate(results):
            task_type, file_path = task_metadata[i]

            if isinstance(task_result, dict):
                status = task_result.get("status", "unknown")

                if status == "success":
                    completed_tasks += 1
                    self.stdout.write(self.style.SUCCESS(f"✓ {task_type}: {file_path}"))
                elif status == "skipped":
                    skipped_tasks += 1
                    reason = task_result.get("reason", "Skipped")
                    self.stdout.write(
                        self.style.WARNING(f"⊘ {task_type}: {file_path} - {reason}")
                    )
                elif status == "error":
                    failed_tasks += 1
                    error = task_result.get("error", "Unknown error")
                    self.stdout.write(
                        self.style.ERROR(f"✗ {task_type}: {file_path} - {error}")
                    )
                else:
                    failed_tasks += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ {task_type}: {file_path} - Unknown status: {status}"
                        )
                    )
            else:
                # Task raised an exception
                failed_tasks += 1
                error_msg = str(task_result) if task_result else "Task failed"
                self.stdout.write(
                    self.style.ERROR(f"✗ {task_type}: {file_path} - {error_msg}")
                )

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.SUCCESS(f"Total tasks: {total_tasks}"))
        self.stdout.write(self.style.SUCCESS(f"Completed: {completed_tasks}"))
        if skipped_tasks > 0:
            self.stdout.write(self.style.WARNING(f"Skipped: {skipped_tasks}"))
        if failed_tasks > 0:
            self.stdout.write(self.style.ERROR(f"Failed: {failed_tasks}"))
        self.stdout.write("=" * 60 + "\n")

        if failed_tasks > 0:
            error_msg = f"{failed_tasks} translation tasks failed"
            raise CommandError(error_msg)
