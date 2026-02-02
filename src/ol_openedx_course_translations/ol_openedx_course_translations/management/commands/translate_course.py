"""
Management command to translate course content to a specified language.
"""

import hashlib
import json
import logging
import shutil
import time
from pathlib import Path

from celery import group
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from opaque_keys.edx.locator import CourseLocator

from ol_openedx_course_translations.models import CourseTranslationLog
from ol_openedx_course_translations.tasks import (
    translate_file_task,
    translate_grading_policy_task,
    translate_policy_json_task,
)
from ol_openedx_course_translations.utils.constants import (
    ES_419_LANGUAGE_CODE,
    ES_LANGUAGE_CODE,
    PROVIDER_DEEPL,
)
from ol_openedx_course_translations.utils.course_translations import (
    create_translated_archive,
    create_translated_copy,
    extract_course_archive,
    generate_course_key_from_xml,
    get_translatable_file_paths,
    update_course_language_attribute,
    validate_course_inputs,
)

logger = logging.getLogger(__name__)

# Task configuration
TASK_TIMEOUT_SECONDS = 3600 * 2  # 2 hour total timeout for all tasks
TASK_POLL_INTERVAL_SECONDS = 2  # Poll every 2 seconds for task completion
BATCH_SIZE = 20  # Process 20 tasks at a time


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
        self.content_glossary = None
        self.srt_glossary = None
        self.keep_failure = False
        self.translation_validation_provider_name = None
        self.translation_validation_model = None

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
            "--translation-validation-provider",
            dest="translation_validation_provider",
            required=False,
            help=(
                "Optional provider to validate and fix the generated content translations by the primary provider. "  # noqa: E501
                "Format: 'PROVIDER', or 'PROVIDER/MODEL' "
                "(e.g., 'openai', 'openai/gpt-5.2', 'gemini', 'gemini/gemini-3-pro-preview'). "  # noqa: E501
                "If omitted, no post-translation validation is performed."
            ),
        )
        parser.add_argument(
            "--content-glossary",
            dest="content_glossary",
            required=False,
            help=(
                "Path to glossary directory for content (XML/HTML and text) "
                "translation. Should contain language-specific glossary files."
            ),
        )
        parser.add_argument(
            "--srt-glossary",
            dest="srt_glossary",
            required=False,
            help=(
                "Path to glossary directory for SRT subtitle translation. "
                "Should contain language-specific glossary files."
            ),
        )
        parser.add_argument(
            "--keep_failure",
            dest="keep_failure",
            required=False,
            default=False,
            action="store_true",
            help=("Keep failed translation files instead of deleting them."),
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

    def handle(self, **options) -> None:  # noqa: PLR0915
        """Handle the translate_course command."""
        try:
            start_time = time.perf_counter()
            course_archive_path = Path(options["course_archive_path"])
            source_language = options["source_language"].upper()
            target_language = options["target_language"].upper()

            # Normalize Spanish language codes to es-419
            if target_language in (ES_LANGUAGE_CODE, ES_419_LANGUAGE_CODE):
                target_language = ES_419_LANGUAGE_CODE

            content_provider_spec = options["content_translation_provider"]
            srt_provider_spec = options["srt_translation_provider"]
            translation_validation_provider_spec = options.get(
                "translation_validation_provider"
            )
            self.content_glossary = options.get("content_glossary")
            self.srt_glossary = options.get("srt_glossary")
            self.keep_failure = options.get("keep_failure", False)

            # Parse and validate provider specifications (includes validation)
            content_provider_name, content_model = (
                self._parse_and_validate_provider_spec(content_provider_spec)
            )
            srt_provider_name, srt_model = self._parse_and_validate_provider_spec(
                srt_provider_spec
            )
            translation_validation_provider_name = None
            translation_validation_model = None
            if translation_validation_provider_spec:
                (
                    translation_validation_provider_name,
                    translation_validation_model,
                ) = self._parse_and_validate_provider_spec(
                    translation_validation_provider_spec
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

            if translation_validation_provider_name:
                if translation_validation_model:
                    self.stdout.write(
                        "Content translation validation provider: "
                        f"{translation_validation_provider_name}/{translation_validation_model}"
                    )
                else:
                    self.stdout.write(
                        f"Content translation validation provider: {translation_validation_provider_name}"  # noqa: E501
                    )

            # Validate inputs
            validate_course_inputs(course_archive_path)

            # Store provider names and models
            self.content_provider_name = content_provider_name
            self.content_model = content_model
            self.srt_provider_name = srt_provider_name
            self.srt_model = srt_model
            self.translation_validation_provider_name = (
                translation_validation_provider_name
            )
            self.translation_validation_model = translation_validation_model

            # Resolve base directory from settings (string) and ensure it exists
            base_dir_setting = getattr(
                settings,
                "COURSE_TRANSLATIONS_BASE_DIR",
                "/openedx/data/course_translations",
            )
            course_translations_base_dir = Path(base_dir_setting)
            course_translations_base_dir.mkdir(parents=True, exist_ok=True)

            # Extract course archive into fixed base directory
            extracted_course_dir = extract_course_archive(
                course_archive_path, extract_to_dir=course_translations_base_dir
            )

            # Create translated copy (also under fixed base directory)
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

            source_course_id = generate_course_key_from_xml(
                course_dir_path=self.translated_course_dir
            )

            # Add translation log entry
            self._add_translation_log_entry(
                source_language=source_language,
                target_language=target_language,
                command_stats=command_stats,
                source_course_id=source_course_id,
            )

            # Write translations metadata into the translated course output
            self._write_translations_meta_file(
                course_dir=translated_course_dir,
                source_language=source_language,
                target_language=target_language,
                command_stats=command_stats,
                command_options=options,
                source_course_id=source_course_id,
            )

            # Create final archive in the same fixed base directory
            translated_archive_path = create_translated_archive(
                translated_course_dir,
                target_language,
                course_archive_path.stem,
                output_dir=course_translations_base_dir,
            )
            success_msg = (
                f"Translation completed successfully. Translated archive created: "
                f"{translated_archive_path}"
            )
            self.stdout.write(self.style.SUCCESS(success_msg))

        except Exception as e:
            logger.exception("Translation failed")

            # Cleanup translated course directory on failure
            if (
                self.translated_course_dir
                and self.translated_course_dir.exists()
                and not self.keep_failure
            ):
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
                self.content_glossary,
                self.srt_glossary,
                self.translation_validation_provider_name,
                self.translation_validation_model,
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
                    self.content_glossary,
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
                    self.content_glossary,
                )
                self.tasks.append(("policy", str(policy_file), task))
                logger.info("Added policy.json task for: %s", policy_file)

    def _wait_and_report_tasks(self) -> list[str]:  # noqa: C901, PLR0915, PLR0912
        """
        Execute all tasks as Celery groups in batches and wait for completion.

        Processes tasks in batches of 20. If any task fails in a batch,
        the command fails immediately.

        Raises:
            CommandError: If any tasks fail
        """
        stats = []
        if not self.tasks:
            self.stdout.write("No tasks to execute.")
            return []

        total_tasks = len(self.tasks)
        self.stdout.write(
            f"\nExecuting {total_tasks} translation tasks in batches of {BATCH_SIZE}...\n"  # noqa: E501
        )

        # Process tasks in batches
        completed_tasks = 0
        failed_tasks = 0
        skipped_tasks = 0

        for batch_start in range(0, total_tasks, BATCH_SIZE):
            batch_end = min(batch_start + BATCH_SIZE, total_tasks)
            batch_tasks = self.tasks[batch_start:batch_end]
            batch_num = (batch_start // BATCH_SIZE) + 1
            total_batches = (total_tasks + BATCH_SIZE - 1) // BATCH_SIZE

            self.stdout.write(
                f"\nProcessing batch {batch_num}/{total_batches} "
                f"(tasks {batch_start + 1}-{batch_end})..."
            )

            # Extract task signatures and create mappings for this batch
            task_signatures = [task_sig for _, _, task_sig in batch_tasks]
            task_metadata = {
                i: (task_type, file_path)
                for i, (task_type, file_path, _) in enumerate(batch_tasks)
            }

            # Create and execute group for this batch
            job = group(task_signatures)
            result = job.apply_async()

            # Wait for batch to complete with progress reporting
            batch_completed = 0
            self.stdout.flush()

            try:
                # Poll for completion and show progress
                while not result.ready():
                    # Count completed tasks in this batch
                    new_completed = sum(1 for r in result.results if r.ready())
                    if new_completed > batch_completed:
                        batch_completed = new_completed
                        overall_completed = (
                            completed_tasks + skipped_tasks + batch_completed
                        )
                        self.stdout.write(
                            f"\rProgress: {overall_completed}/{total_tasks} tasks completed\n",  # noqa: E501
                            ending="",
                        )
                        self.stdout.flush()

                    # Sleep before next poll
                    time.sleep(TASK_POLL_INTERVAL_SECONDS)

                # Get all results (propagate=False to handle errors manually)
                results = result.get(timeout=TASK_TIMEOUT_SECONDS, propagate=False)

            except Exception as e:
                logger.exception("Batch execution failed")
                error_msg = f"Batch execution timeout or error: {e}"
                raise CommandError(error_msg) from e

            # Process batch results
            batch_failed = False

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
                        batch_failed = True
                        error = task_result.get("error", "Unknown error")
                        msg = f"✗ {task_type}: {file_path} - {error}"
                        stats.append(msg)
                        self.stdout.write(self.style.ERROR(msg))
                    else:
                        failed_tasks += 1
                        batch_failed = True
                        msg = f"✗ {task_type}: {file_path} - Unknown status: {status}"
                        stats.append(msg)
                        self.stdout.write(self.style.ERROR(msg))
                else:
                    # Task raised an exception
                    failed_tasks += 1
                    batch_failed = True
                    error_msg = str(task_result) if task_result else "Task failed"
                    msg = f"✗ {task_type}: {file_path} - {error_msg}"
                    stats.append(msg)
                    self.stdout.write(self.style.ERROR(msg))

            # If any task in this batch failed, stop processing
            if batch_failed:
                self.stdout.write("\n" + "=" * 60)
                self.stdout.write(
                    self.style.ERROR(f"Batch {batch_num} failed. Stopping execution.")
                )
                failure_summary = (
                    f"Total tasks processed: {completed_tasks + skipped_tasks + failed_tasks}\n"  # noqa: E501
                    f"Completed: {completed_tasks}\n"
                    f"Skipped: {skipped_tasks}\n"
                    f"Failed: {failed_tasks}"
                )
                stats.append(failure_summary)
                self.stdout.write(failure_summary)
                self.stdout.write("=" * 60 + "\n")
                error_msg = (
                    f"{failed_tasks} translation task(s) failed in batch {batch_num}"
                )
                raise CommandError(error_msg)

        # Print summary (only reached if all batches succeed)
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
        self.stdout.write("=" * 60 + "\n")

        return stats

    def _add_translation_log_entry(
        self, source_language, target_language, source_course_id, command_stats=None
    ) -> None:
        """
        Add a log entry for the course translation operation.

        Args:
            source_language: Source language code
            target_language: Target language code
            command_stats: List of command statistics/logs
            source_course_id: Source course id
        """
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

    def _write_translations_meta_file(  # noqa: PLR0913
        self,
        *,
        course_dir: Path,
        source_language: str,
        target_language: str,
        command_stats: list[str] | None,
        command_options: dict | None = None,
        source_course_id: CourseLocator,
    ) -> None:
        """
        Write a metadata file into <course_dir>/course/static/translations_meta.txt.

        Contains:
          - source_language
          - target_language
          - command_options (resolved options, incl. defaults)
          - command_stats
          - Source course id

        Args:
            course_dir: Path to the course directory
            source_language: Source language code
            target_language: Target language code
            command_stats: List of command statistics/logs
            command_options: Dictionary of command options used
            source_course_id: Source course id
        """
        static_dir = course_dir / "course" / "static"
        static_dir.mkdir(parents=True, exist_ok=True)

        meta_path = static_dir / ".translations_meta"
        stats_text = "\n".join(command_stats) if command_stats else ""

        options_lines = []
        if command_options:
            # Stable, readable ordering
            for key in sorted(command_options.keys()):
                value = command_options.get(key)
                options_lines.append(f"{key}: {value}")
        options_text = "\n".join(options_lines)

        meta_contents = (
            f"source_course_id: {source_course_id}\n"
            f"source_language: {source_language}\n"
            f"target_language: {target_language}\n\n"
            f"Content Provider: {self.content_provider_name}\n"
            f"Content Model: {self.content_model}\n"
            f"SRT Provider: {self.srt_provider_name}\n"
            f"SRT Model: {self.srt_model}\n"
            f"Validation Provider: {self.translation_validation_provider_name}\n"
            f"Validation Model: {self.translation_validation_model}\n\n"
            "COMMAND_OPTIONS:\n"
            f"{options_text}\n\n"
            "COMMAND_STATS:\n"
            f"{stats_text}\n"
        )

        meta_path.write_text(meta_contents, encoding="utf-8")

        # Compute custom_md5 for the meta contents
        content = type("Content", (), {"data": meta_contents})()
        encoded_data = content.data.encode("utf-8")
        meta_custom_md5 = hashlib.md5(encoded_data).hexdigest()  # noqa: S324

        # Upsert into policies/assets.json
        policies_dir = course_dir / "course" / "policies"
        policies_dir.mkdir(parents=True, exist_ok=True)
        assets_path = policies_dir / "assets.json"

        assets = {}
        if assets_path.exists():
            try:
                assets = json.loads(assets_path.read_text(encoding="utf-8") or "{}")
            except Exception:
                logger.exception(
                    "Failed to parse policies/assets.json;"
                )
                return  # Skip updating assets.json on parse failure

        asset_key = ".translations_meta"
        assets[asset_key] = {
            "contentType": "text/plain",
            "content_son": {
                "category": "asset",
                "course": source_course_id.course,
                "name": asset_key,
                "org": source_course_id.org,
                "revision": None,
                "run": source_course_id.run,
                "tag": "c4x",
            },
            "custom_md5": meta_custom_md5,
            "displayname": asset_key,
            "filename": f"asset-v1:{source_course_id}+type@asset+block@{asset_key}"
            if source_course_id
            else asset_key,
            "import_path": None,
            "locked": True,
            "thumbnail_location": None,
        }

        assets_path.write_text(
            json.dumps(assets, indent=4, sort_keys=True) + "\n", encoding="utf-8"
        )
