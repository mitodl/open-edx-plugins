"""
Management command to translate course content to a specified language.
"""

import logging
import shutil
import time
from pathlib import Path

from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from ol_openedx_course_translations.models import CourseTranslationLog
from ol_openedx_course_translations.tasks import (
    translate_file_task,
    translate_grading_policy_task,
    translate_policy_json_task,
)
from ol_openedx_course_translations.utils.constants import PROVIDER_DEEPL
from ol_openedx_course_translations.utils.course_translations import (
    create_translated_archive,
    create_translated_copy,
    extract_course_archive,
    generate_course_id_from_xml,
    get_translatable_file_paths,
    update_course_language_attribute,
    validate_course_inputs,
)

logger = logging.getLogger(__name__)

# Task configuration
TASK_TIMEOUT_SECONDS = 3600 * 2  # 2 hour total timeout for all tasks
TASK_POLL_INTERVAL_SECONDS = 2  # Poll every 2 seconds for task completion


class Command(BaseCommand):
    """Translate given course content to the specified language."""

    help = (
        "Translate course content to the specified language.\n\n"
        "Configuration:\n"
        "All translation providers should be configured in TRANSLATIONS_PROVIDERS:\n"
        "{\n"
        '    "deepl": {"api_key": "<YOUR_DEEPL_API_KEY>"},\n'
        '    "openai": {"api_key": "<KEY>", "default_model": "gpt-5.2"},\n'
        '    "gemini": {"api_key": "<KEY>", "default_model": "gemini-3-pro-preview"},\n'
        '    "mistral": {"api_key": "<KEY>", "default_model": "mistral-large-latest"}\n'
        "}\n"
    )

    def __init__(self, *args, **kwargs):
        """Initialize the command with empty task list."""
        super().__init__(*args, **kwargs)
        self.tasks = []
        self.translated_course_dir = None
        self.content_provider_name = None
        self.content_model = None
        self.srt_provider_name = None
        self.srt_model = None
        self.glossary_directory = None

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
                "Format: 'deepl', 'PROVIDER', or 'PROVIDER/MODEL' "
                "(e.g., 'openai', 'openai/gpt-5.2', 'gemini', 'gemini/gemini-3-pro-preview'). "  # noqa: E501
                "If model is not specified, uses the default model from settings."
            ),
        )
        parser.add_argument(
            "--srt-translation-provider",
            dest="srt_translation_provider",
            required=True,
            help=(
                "Translation provider for SRT subtitles. "
                "Format: 'deepl', 'PROVIDER', or 'PROVIDER/MODEL' "
                "(e.g., 'openai', 'openai/gpt-5.2', 'gemini', 'gemini/gemini-3-pro-preview'). "  # noqa: E501
                "If model is not specified, uses the default model from settings."
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

    def _parse_and_validate_provider_spec(
        self, provider_spec: str
    ) -> tuple[str, str | None]:
        """
        Parse and validate provider specification into provider name and model.

        Resolves model from settings if not provided in specification.

        Args:
            provider_spec: Provider specification

        Returns:
            Tuple of (provider_name, model_name). model_name is None for DeepL or
            resolved from settings if not specified.

        Raises:
            CommandError: If provider specification format is invalid
            or model and api_key cannot be resolved
        """
        # Parse the specification
        if "/" in provider_spec:
            parts = provider_spec.split("/", 1)
            if len(parts) != 2 or not parts[0] or not parts[1]:  # noqa: PLR2004
                error_msg = (
                    f"Invalid provider specification: {provider_spec}. "
                    "Use format 'PROVIDER' or 'PROVIDER/MODEL' "
                    "(e.g., 'openai', 'openai/gpt-5.2')"
                )
                raise CommandError(error_msg)
            provider_name = parts[0].lower()
            model_name = parts[1]
        else:
            provider_name = provider_spec.lower()
            model_name = None

        # Try to get default model from settings
        providers_config = getattr(settings, "TRANSLATIONS_PROVIDERS", {})
        if provider_name not in providers_config:
            error_msg = (
                f"Provider '{provider_name}' not configured in TRANSLATIONS_PROVIDERS. "
                f"Available providers: {', '.join(providers_config.keys())}"
            )
            raise CommandError(error_msg)

        provider_config = providers_config[provider_name]
        api_key = provider_config.get("api_key")
        if not api_key:
            error_msg = (
                f"API key for provider '{provider_name}' is not configured in "
                "TRANSLATIONS_PROVIDERS. Please set the 'api_key' in settings."
            )
            raise CommandError(error_msg)

        # DeepL doesn't use models
        if provider_name == PROVIDER_DEEPL:
            return provider_name, None

        # If model is explicitly provided, return it
        if model_name:
            return provider_name, model_name

        default_model = provider_config.get("default_model")
        if not default_model:
            error_msg = (
                f"No model specified for provider '{provider_name}' and no "
                f"default_model found in TRANSLATIONS_PROVIDERS['{provider_name}']. "
                f"Either specify a model (e.g., '{provider_name}/gpt-5.2') or "
                f"configure a default_model in settings."
            )
            raise CommandError(error_msg)

        return provider_name, default_model

    def handle(self, **options) -> None:
        """Handle the translate_course command."""
        try:
            start_time = time.perf_counter()
            course_archive_path = Path(options["course_archive_path"])
            source_language = options["source_language"]
            target_language = options["target_language"].upper()
            content_provider_spec = options["content_translation_provider"]
            srt_provider_spec = options["srt_translation_provider"]
            glossary_directory = options.get("glossary_directory")

            # Parse and validate provider specifications (includes validation)
            content_provider_name, content_model = (
                self._parse_and_validate_provider_spec(content_provider_spec)
            )
            srt_provider_name, srt_model = self._parse_and_validate_provider_spec(
                srt_provider_spec
            )

            # Log the resolved configuration
            if content_model:
                self.stdout.write(
                    f"Content provider: {content_provider_name}/{content_model}"
                )
            else:
                self.stdout.write(f"Content provider: {content_provider_name}")

            if srt_model:
                self.stdout.write(f"SRT provider: {srt_provider_name}/{srt_model}")
            else:
                self.stdout.write(f"SRT provider: {srt_provider_name}")

            # Validate inputs
            validate_course_inputs(course_archive_path)

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

            # Store for cleanup on failure
            self.translated_course_dir = translated_course_dir

            # Delete extracted directory after copying
            if extracted_course_dir.exists():
                shutil.rmtree(extracted_course_dir)

            # Translate content asynchronously
            self._translate_course_content_async(
                translated_course_dir, source_language, target_language
            )

            # Wait for all tasks and report status
            command_stats = self._wait_and_report_tasks()
            total_time_taken_msg = (
                f"Command finished in: {time.perf_counter() - start_time:.2f} seconds."
            )
            self.stdout.write(self.style.SUCCESS(total_time_taken_msg))
            command_stats.append(total_time_taken_msg)

            # Add translation log entry
            self._add_translation_log_entry(
                source_language=source_language,
                target_language=target_language,
                command_stats=command_stats,
            )
            # Create final archive
            translated_archive_path = create_translated_archive(
                translated_course_dir, target_language, course_archive_path.stem
            )
            success_msg = (
                f"Translation completed successfully. Translated archive created: "
                f"{translated_archive_path}"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))

        except Exception as e:
            logger.exception("Translation failed")

            # Cleanup translated course directory on failure
            if self.translated_course_dir and self.translated_course_dir.exists():
                self.stdout.write(
                    self.style.WARNING(
                        f"Cleaning up translated course directory: {self.translated_course_dir}"  # noqa: E501
                    )
                )
                shutil.rmtree(self.translated_course_dir)

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

    def _wait_and_report_tasks(self) -> list[str]:  # noqa: C901, PLR0915, PLR0912
        """
        Execute all tasks as a Celery group and wait for completion.

        Uses Celery's group primitive to execute tasks in parallel and
        provides detailed progress reporting.

        Raises:
            CommandError: If any tasks fail
        """
        stats = []
        if not self.tasks:
            self.stdout.write("No tasks to execute.")
            return []

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

        # Wait for all tasks to complete with progress reporting
        completed_count = 0
        self.stdout.flush()

        try:
            # Poll for completion and show progress
            while not result.ready():
                # Count completed tasks
                new_completed = sum(1 for r in result.results if r.ready())
                if new_completed > completed_count:
                    completed_count = new_completed
                    self.stdout.write(
                        f"\rProgress: {completed_count}/{total_tasks} tasks completed",
                        ending="",
                    )
                    self.stdout.flush()

                # Sleep before next poll (don't use join with timeout)
                time.sleep(TASK_POLL_INTERVAL_SECONDS)

            # Final update
            self.stdout.write(
                f"\rProgress: {total_tasks}/{total_tasks} tasks completed\n"
            )

            # Get all results (this will raise exceptions if propagate=True)
            results = result.get(timeout=TASK_TIMEOUT_SECONDS, propagate=False)

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
                    msg = f"✓ {task_type}: {file_path}"
                    stats.append(msg)
                    self.stdout.write(self.style.SUCCESS(msg))
                elif status == "skipped":
                    skipped_tasks += 1
                    reason = task_result.get("reason", "Skipped")
                    msg = f"⊘ {task_type}: {file_path} - {reason}"
                    stats.append(msg)
                    self.stdout.write(self.style.WARNING(msg))
                elif status == "error":
                    failed_tasks += 1
                    error = task_result.get("error", "Unknown error")
                    msg = f"✗ {task_type}: {file_path} - {error}"
                    stats.append(msg)
                    self.stdout.write(self.style.ERROR(msg))
                else:
                    failed_tasks += 1
                    msg = f"✗ {task_type}: {file_path} - Unknown status: {status}"
                    stats.append(msg)
                    self.stdout.write(self.style.ERROR(msg))
            else:
                # Task raised an exception
                failed_tasks += 1
                error_msg = str(task_result) if task_result else "Task failed"
                msg = f"✗ {task_type}: {file_path} - {error_msg}"
                stats.append(msg)
                self.stdout.write(self.style.ERROR(msg))

        # Print summary
        self.stdout.write("\n" + "=" * 60)
        successful_tasks_stats = (
            f"Total tasks: {total_tasks}\nCompleted: {completed_tasks}"
        )
        stats.append(successful_tasks_stats)
        self.stdout.write(self.style.SUCCESS(successful_tasks_stats))
        if skipped_tasks > 0:
            skipped_tasks_stats = f"Skipped: {skipped_tasks}"
            stats.append(skipped_tasks_stats)
            self.stdout.write(self.style.WARNING(skipped_tasks_stats))
        if failed_tasks > 0:
            failed_tasks_stats = f"Failed: {failed_tasks}"
            stats.append(failed_tasks_stats)
            self.stdout.write(self.style.ERROR(failed_tasks_stats))
        self.stdout.write("=" * 60 + "\n")

        if failed_tasks > 0:
            error_msg = f"{failed_tasks} translation tasks failed"
            raise CommandError(error_msg)

        return stats

    def _add_translation_log_entry(
        self, source_language, target_language, command_stats=None
    ) -> None:
        """
        Add a log entry for the course translation operation.

        Args:
            source_language: Source language code
            target_language: Target language code
            command_stats: List of command statistics/logs
        """
        source_course_id = generate_course_id_from_xml(
            course_dir_path=self.translated_course_dir
        )
        command_stats_str = "\n".join(command_stats) if command_stats else ""

        CourseTranslationLog.objects.create(
            source_course_id=source_course_id,
            source_course_language=source_language,
            target_course_language=target_language,
            srt_provider_name=self.srt_provider_name,
            srt_provider_model=self.srt_model or "",
            content_provider_name=self.content_provider_name,
            content_provider_model=self.content_model or "",
            command_stats=command_stats_str,
        )
