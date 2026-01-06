"""
Management command to translate course content to a specified language.
"""

import logging
import shutil
import time
from pathlib import Path

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
    get_translation_provider,
    update_course_language_attribute,
    validate_course_inputs,
)

logger = logging.getLogger(__name__)

# Task configuration
TASK_TIMEOUT_SECONDS = 600  # 10 minutes
TASK_POLL_INTERVAL_SECONDS = 2


class Command(BaseCommand):
    """Translate given course content to the specified language."""

    help = "Translate course content to the specified language."

    def __init__(self, *args, **kwargs):
        """Initialize the command with empty task results list."""
        super().__init__(*args, **kwargs)
        self.task_results = []

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

            # Store provider names and models
            self.content_provider_name = content_provider_name
            self.content_model = content_model
            self.srt_provider_name = srt_provider_name
            self.srt_model = srt_model
            self.glossary_directory = glossary_directory

            # Validate providers by attempting to instantiate them
            try:
                get_translation_provider(
                    content_provider_name,
                    content_model,
                )
                get_translation_provider(
                    srt_provider_name,
                    srt_model,
                )
            except ValueError as e:
                raise CommandError(str(e)) from e

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

        # Dispatch translation tasks for files in course directory
        self._dispatch_file_translation_tasks(
            course_directory, source_language, target_language, recursive=False
        )

        # Dispatch translation tasks for target subdirectories
        for target_dir_name in settings.COURSE_TRANSLATIONS_TARGET_DIRECTORIES:
            target_directory = course_directory / target_dir_name
            if target_directory.exists() and target_directory.is_dir():
                self._dispatch_file_translation_tasks(
                    target_directory, source_language, target_language, recursive=True
                )

        # Dispatch tasks for special JSON files
        self._dispatch_grading_policy_tasks(course_dir, target_language)
        self._dispatch_policy_json_tasks(course_dir, target_language)

    def _dispatch_file_translation_tasks(
        self,
        directory_path: Path,
        source_language: str,
        target_language: str,
        *,
        recursive: bool = False,
    ) -> None:
        """
        Dispatch Celery tasks for file translation.

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
            task_result = translate_file_task.delay(
                str(file_path),
                source_language,
                target_language,
                self.content_provider_name,
                self.content_model,
                self.srt_provider_name,
                self.srt_model,
                self.glossary_directory,
            )
            self.task_results.append(("file", str(file_path), task_result))
            logger.info("Dispatched translation task for: %s", file_path)

    def _dispatch_grading_policy_tasks(
        self, course_dir: Path, target_language: str
    ) -> None:
        """
        Dispatch Celery tasks for grading_policy.json translation.

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
                task_result = translate_grading_policy_task.delay(
                    str(grading_policy_file),
                    target_language,
                    self.content_provider_name,
                    self.content_model,
                    self.glossary_directory,
                )
                self.task_results.append(
                    ("grading_policy", str(grading_policy_file), task_result)
                )
                logger.info(
                    "Dispatched grading policy task for: %s", grading_policy_file
                )

    def _dispatch_policy_json_tasks(
        self, course_dir: Path, target_language: str
    ) -> None:
        """
        Dispatch Celery tasks for policy.json translation.

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
                task_result = translate_policy_json_task.delay(
                    str(policy_file),
                    target_language,
                    self.content_provider_name,
                    self.content_model,
                    self.glossary_directory,
                )
                self.task_results.append(("policy", str(policy_file), task_result))
                logger.info("Dispatched policy.json task for: %s", policy_file)

    def _wait_and_report_tasks(self) -> None:  # noqa: C901, PLR0912, PLR0915
        """
        Wait for all Celery tasks to complete and report their status.

        Monitors task progress, handles timeouts, and provides detailed status reports.

        Raises:
            CommandError: If any tasks fail or timeout occurs
        """
        if not self.task_results:
            self.stdout.write("No tasks to wait for.")
            return

        self.stdout.write(
            f"\nDispatched {len(self.task_results)} tasks. Waiting for completion...\n"
        )

        total_tasks = len(self.task_results)
        completed_tasks = 0
        failed_tasks = 0
        skipped_tasks = 0

        # Create a mapping of task_id to task info for quick lookup
        task_info = {
            task_result.id: (task_type, file_path)
            for task_type, file_path, task_result in self.task_results
        }

        # Get all AsyncResult objects
        pending_tasks = {
            task_result.id: task_result for _, _, task_result in self.task_results
        }

        # Poll for task completion
        start_time = time.time()

        while pending_tasks:
            completed_in_iteration = []

            for task_id, task_result in list(pending_tasks.items()):
                if task_result.ready():
                    completed_in_iteration.append(task_id)
                    task_type, file_path = task_info[task_id]

                    try:
                        result = task_result.get(timeout=1)

                        if result["status"] == "success":
                            completed_tasks += 1
                            self.stdout.write(
                                self.style.SUCCESS(f"✓ {task_type}: {file_path}")
                            )
                        elif result["status"] == "skipped":
                            skipped_tasks += 1
                            self.stdout.write(
                                self.style.WARNING(
                                    f"⊘ {task_type}: {file_path} - "
                                    f"{result.get('reason', 'Skipped')}"
                                )
                            )
                        else:
                            failed_tasks += 1
                            error = result.get("error", "Unknown error")
                            self.stdout.write(
                                self.style.ERROR(
                                    f"✗ {task_type}: {file_path} - {error}"
                                )
                            )
                    except (TimeoutError, KeyError, TypeError) as e:
                        failed_tasks += 1
                        self.stdout.write(
                            self.style.ERROR(
                                f"✗ {task_type}: {file_path} - Task failed: {e}"
                            )
                        )

            # Remove completed tasks from pending
            for task_id in completed_in_iteration:
                del pending_tasks[task_id]

            # Check for timeout
            if time.time() - start_time > TASK_TIMEOUT_SECONDS * total_tasks:
                self.stdout.write(
                    self.style.ERROR(
                        f"\nTimeout: {len(pending_tasks)} tasks did not complete"
                    )
                )
                failed_tasks += len(pending_tasks)
                break

            # Sleep before next poll if there are still pending tasks
            if pending_tasks:
                time.sleep(TASK_POLL_INTERVAL_SECONDS)

                # Show progress
                completed_count = total_tasks - len(pending_tasks)
                self.stdout.write(
                    f"Progress: {completed_count}/{total_tasks} tasks completed\r",
                    ending="",
                )
                self.stdout.flush()

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
