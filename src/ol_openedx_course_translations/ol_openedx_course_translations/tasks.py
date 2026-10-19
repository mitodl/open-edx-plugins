"""Celery tasks for course content translation."""

import json
import logging
import re
from functools import lru_cache
from pathlib import Path

from celery import shared_task
from defusedxml import ElementTree
from django.conf import settings

from ol_openedx_course_translations.models import (
    TranslationBenchmark,
    TranslationBenchmarkCandidate,
)
from ol_openedx_course_translations.providers.base import TRANSIENT_PROVIDER_ERRORS
from ol_openedx_course_translations.providers.llm_providers import (
    NO_CLIENT_RETRIES,
    TRANSLATION_MARKER_END,
    TRANSLATION_MARKER_START,
)
from ol_openedx_course_translations.utils.benchmark import (
    BENCHMARK_TAG_HANDLING,
    Benchmark,
    BenchmarkError,
    read_benchmark,
    units_and_elements,
)
from ol_openedx_course_translations.utils.constants import (
    ENGLISH_LANGUAGE_CODE,
    XML_FORMAT_ATTR,
)
from ol_openedx_course_translations.utils.course_translations import (
    apply_format_attribute_mapping,
    get_srt_output_filename,
    get_translation_provider,
    looks_like_markup,
    translate_policy_fields,
    update_video_xml_complete,
)

logger = logging.getLogger(__name__)

TRANSLATE_FILE_TASK_LIMITS = getattr(
    settings,
    "TRANSLATE_FILE_TASK_LIMITS",
    {
        "soft_time_limit": 9 * 60,  # 9 minutes
        "time_limit": 10 * 60,  # 10 minutes
        "max_retries": 1,  # 1 Initial try + 1 retry = 2 attempts
        "retry_countdown": 1 * 60,  # wait 1m before retry
    },
)

# Only a rate limit or timeout is retried. Each task re-raises these ahead of
# its catch-all, or autoretry_for never sees them.
TRANSIENT_RETRY = {
    "autoretry_for": TRANSIENT_PROVIDER_ERRORS,
    "retry_kwargs": {
        "max_retries": TRANSLATE_FILE_TASK_LIMITS["max_retries"],
        "countdown": TRANSLATE_FILE_TASK_LIMITS["retry_countdown"],
    },
    "retry_backoff": False,
}


def _parse_marker_wrapped_translation(raw_text: str) -> str | None:
    """
    Parse translation text wrapped in specific start/end markers.
    """
    if not raw_text:
        return None

    # Tolerant pattern (handles whitespace/newlines and any provider echo)
    pattern = re.compile(
        re.escape(TRANSLATION_MARKER_START)
        + r"(.*?)"
        + re.escape(TRANSLATION_MARKER_END),
        flags=re.DOTALL,
    )
    match = pattern.search(raw_text)
    if match:
        return match.group(1).strip()

    # Case-insensitive fallback (some providers might alter marker casing)
    pattern_case_insensitive = re.compile(
        re.escape(TRANSLATION_MARKER_START)
        .replace("TRANSLATION", "translation")
        .replace("START", "start")
        + r"(.*?)"
        + re.escape(TRANSLATION_MARKER_END)
        .replace("TRANSLATION", "translation")
        .replace("END", "end"),
        flags=re.DOTALL,
    )
    match_ci = pattern_case_insensitive.search(raw_text)
    if match_ci:
        return match_ci.group(1).strip()

    return None


@shared_task(
    bind=True,
    name="translate_file_task",
    soft_time_limit=TRANSLATE_FILE_TASK_LIMITS["soft_time_limit"],
    time_limit=TRANSLATE_FILE_TASK_LIMITS["time_limit"],
    **TRANSIENT_RETRY,
)
def translate_file_task(  # noqa: PLR0913, PLR0917, PLR0912, C901
    _self,
    file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    srt_provider_name: str,
    srt_model: str | None,
    content_glossary: str | None = None,
    srt_glossary: str | None = None,
    translation_validation_provider_name: str | None = None,
    translation_validation_model: str | None = None,
    grading_type_mapping: dict[str, str] | None = None,
):
    """
    Translate a single file asynchronously.

    Handles translation of various file types including SRT subtitles,
    XML, and HTML files. Uses appropriate translation provider based on file type.

    Args:
        _self: Celery task instance (bound)
        file_path_str: Path to the file to translate
        source_language: Source language code
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        srt_provider_name: Provider name for SRT translation
        srt_model: Model name for SRT provider (optional)
        content_glossary: Path to glossary directory for content (optional)
        srt_glossary: Path to glossary directory for SRT (optional)
        translation_validation_provider_name: Provider name for post-translation
            validation (optional)
        translation_validation_model: Model name for validation provider (optional)
        grading_type_mapping: Mapping of original grading type values to their
            translated equivalents from the grading policy file. When provided,
            the ``format`` attribute of XML files is replaced with the
            consistent grading-policy translation instead of relying on the
            translation provider. (optional)

    Returns:
        Dict with status, file path, and optional error or output information
    """
    try:
        file_path = Path(file_path_str)

        # Handle SRT files
        if file_path.suffix == ".srt":
            provider = get_translation_provider(srt_provider_name, srt_model)

            source_lang_pattern = f"-{source_language}.srt"
            if not file_path.name.endswith(source_lang_pattern):
                return {
                    "status": "skipped",
                    "file": file_path_str,
                    "reason": "Not source language SRT",
                }

            output_filename = get_srt_output_filename(file_path.name, target_language)
            output_file_path = file_path.parent / output_filename

            provider.translate_document(
                file_path,
                output_file_path,
                source_language,
                target_language,
                srt_glossary,
            )

            return {
                "status": "success",
                "file": file_path_str,
                "output": str(output_file_path),
            }

        # Handle other files
        file_content = file_path.read_text(encoding="utf-8")

        # Capture original format attribute before translation so we can
        # override it with the pre-translated grading policy value later.
        original_format_value = None
        if file_path.suffix == ".xml" and grading_type_mapping:
            try:
                xml_root = ElementTree.fromstring(file_content)
                original_format_value = xml_root.attrib.get(XML_FORMAT_ATTR)
            except ElementTree.ParseError:
                pass

        tag_handling_mode = None
        if file_path.suffix in [".xml", ".html"]:
            tag_handling_mode = file_path.suffix.lstrip(".")

        provider = get_translation_provider(content_provider_name, content_model)
        translated_content = provider.translate_text(
            file_content,
            target_language,
            tag_handling=tag_handling_mode,
            glossary_directory=content_glossary,
        )

        # Update video XML if needed (use complete version)
        if file_path.suffix == ".xml" and file_path.parent.name == "video":
            translated_content = update_video_xml_complete(
                translated_content,
                target_language,
            )

        # Post-translation validation/fix for XML/HTML (optional)
        if (
            file_path.suffix in [".xml", ".html"]
            and translation_validation_provider_name
            and translated_content
            and translated_content.strip()
        ):
            validation_provider = get_translation_provider(
                translation_validation_provider_name, translation_validation_model
            )
            validated_content = None
            try:
                validated_response = validation_provider.validate_translation(
                    source_language=source_language,
                    target_language=target_language,
                    source_content=file_content,
                    translated_content=translated_content,
                )
                # validate_translation already parses markers via
                # _parse_text_response, but keep an extra safety parse
                # in case provider returns raw marker-wrapped text.
                validated_content = (
                    _parse_marker_wrapped_translation(validated_response)
                    or validated_response
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(
                    "XML/HTML validation via LLM provider %s failed for %s: %s",
                    translation_validation_provider_name,
                    file_path_str,
                    str(e),
                )
                validated_content = None

            if validated_content is None:
                pass
            elif looks_like_markup(validated_content):
                translated_content = validated_content
            else:
                msg = (
                    "XML/HTML validation provider returned non-markup output for %s; "
                    "keeping original translation. Response snippet: %r"
                )
                logger.warning(
                    msg,
                    file_path_str,
                    (validated_content or "")[:500],
                )

        # Apply the pre-translated grading type mapping to the format attribute
        # to ensure consistency between grading policy and XML content translations.
        if (
            file_path.suffix == ".xml"
            and grading_type_mapping
            and original_format_value
        ):
            translated_content = apply_format_attribute_mapping(
                translated_content,
                original_format_value,
                grading_type_mapping,
            )

        file_path.write_text(translated_content, encoding="utf-8")
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as e:
        logger.exception("Failed to translate file %s", file_path_str)
        return {"status": "error", "file": file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": file_path_str}


@shared_task(bind=True, name="translate_policy_json_task", **TRANSIENT_RETRY)
def translate_policy_json_task(
    _self,
    policy_file_path_str: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    content_glossary: str | None = None,
):
    """
    Translate policy.json file.

    Translates various policy fields including display names, discussion topics,
    learning info, tabs, and XML attributes.

    Args:
        _self: Celery task instance (bound)
        policy_file_path_str: Path to the policy.json file
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        content_glossary: Path to glossary directory for content (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        policy_file_path = Path(policy_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        policy_json_data = json.loads(policy_file_path.read_text(encoding="utf-8"))
        for course_policy_obj in policy_json_data.values():
            if not isinstance(course_policy_obj, dict):
                continue

            translate_policy_fields(
                course_policy_obj, target_language, provider, content_glossary
            )

        policy_file_path.write_text(
            json.dumps(policy_json_data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as e:
        logger.exception("Failed to translate policy.json %s", policy_file_path_str)
        return {"status": "error", "file": policy_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": policy_file_path_str}


@shared_task(bind=True, name="translate_info_updates_task", **TRANSIENT_RETRY)
def translate_info_updates_task(  # noqa: PLR0913, PLR0917, C901
    _self,
    updates_file_path_str: str,
    source_language: str,
    target_language: str,
    content_provider_name: str,
    content_model: str | None,
    content_glossary: str | None = None,
    translation_validation_provider_name: str | None = None,
    translation_validation_model: str | None = None,
):
    """
    Translate info/updates.items.json file.

    Translates the ``content`` field (HTML string) for each update item.

    Args:
        _self: Celery task instance (bound)
        updates_file_path_str: Path to the updates.items.json file
        source_language: Source language code
        target_language: Target language code
        content_provider_name: Provider name for content translation
        content_model: Model name for content provider (optional)
        content_glossary: Path to glossary directory for content (optional)
        translation_validation_provider_name: Provider name for post-translation
            validation (optional)
        translation_validation_model: Model name for validation provider (optional)

    Returns:
        Dict with status, file path, and optional error information
    """
    try:
        updates_file_path = Path(updates_file_path_str)
        provider = get_translation_provider(content_provider_name, content_model)

        updates_data = json.loads(updates_file_path.read_text(encoding="utf-8"))
        if not isinstance(updates_data, list):
            msg = "updates.items.json must contain a list of update items"
            raise TypeError(msg)  # noqa: TRY301

        for update_item in updates_data:
            if not isinstance(update_item, dict):
                continue

            content = update_item.get("content")
            if not isinstance(content, str) or not content.strip():
                continue

            translated_content = provider.translate_text(
                content,
                target_language,
                tag_handling="html",
                glossary_directory=content_glossary,
            )

            if (
                translation_validation_provider_name
                and translated_content
                and translated_content.strip()
            ):
                validation_provider = get_translation_provider(
                    translation_validation_provider_name,
                    translation_validation_model,
                )
                validated_content = None
                try:
                    validated_response = validation_provider.validate_translation(
                        source_language=source_language,
                        target_language=target_language,
                        source_content=content,
                        translated_content=translated_content,
                    )
                    validated_content = (
                        _parse_marker_wrapped_translation(validated_response)
                        or validated_response
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(
                        "updates.items.json validation via provider %s failed "
                        "for %s: %s",
                        translation_validation_provider_name,
                        updates_file_path_str,
                        str(e),
                    )

                if validated_content and looks_like_markup(validated_content):
                    translated_content = validated_content
                elif validated_content is not None:
                    logger.warning(
                        "updates.items.json validation provider returned "
                        "non-markup output for %s; keeping original translation. "
                        "Response snippet: %r",
                        updates_file_path_str,
                        validated_content[:500],
                    )

            update_item["content"] = translated_content

        updates_file_path.write_text(
            json.dumps(updates_data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as e:
        logger.exception(
            "Failed to translate updates.items.json %s", updates_file_path_str
        )
        return {"status": "error", "file": updates_file_path_str, "error": str(e)}
    else:
        return {"status": "success", "file": updates_file_path_str}


# ---------------------------------------------------------------- benchmark

# Longer than llm_providers.VALIDATION_TIMEOUT: a reasoning model reviewing the whole
# benchmark needs it, and with client retries off a slow-but-working model gets
# to finish instead of failing three times.
BENCHMARK_VALIDATION_TIMEOUT = 240

# Benchmark work is dispatched in stages of several hundred tasks, so it runs
# on the low queue: the cms workers are shared with course publishing.
BENCHMARK_QUEUE = "edx.cms.core.low"

# Exception types that mean the code is wrong, rather than the run hitting
# something it already reports. Only these get a traceback: an arm gate raising
# RuntimeError, or a judge reply the parser rejects, is summarised in one line
# by the report itself, and a stack trace per rejected arm buries it.
BUG_LIKE_ERRORS = (AttributeError, IndexError, KeyError, NameError, TypeError)


def _log_benchmark_failure(error: Exception, context: str) -> str:
    """
    Record a task failure and return the string the run will report.

    A traceback is what separates a genuine bug from a provider that timed
    out, since both read the same way in the summary line.
    """
    if isinstance(error, BUG_LIKE_ERRORS):
        logger.exception("benchmark task failed (%s)", context)
    else:
        logger.warning("benchmark task failed (%s): %s", context, error)
    return f"{type(error).__name__}: {error}"


def _benchmark_task(name):
    """Benchmark stage decorator: retries the same errors as TRANSIENT_RETRY."""
    return shared_task(
        bind=True,
        name=name,
        queue=BENCHMARK_QUEUE,
        autoretry_for=TRANSIENT_PROVIDER_ERRORS,
        retry_backoff=True,
        retry_kwargs={"max_retries": 2},
    )


# Runs one worker process keeps a block for — more than one because runs
# overlap on a shared queue, bounded because each entry holds a whole block
# body. An eviction mid-run is not free: the re-read can return republished
# text, or fail outright if the block has gone since.
CACHED_BENCHMARKS = 8


@lru_cache(maxsize=CACHED_BENCHMARKS)
def cached_benchmark(run_id: int) -> Benchmark:
    """
    ``read_benchmark``, once per run per worker process, not once per task.

    Keyed on the run, not the block it names: a Celery child is long-lived,
    so a block-keyed entry would be reused past the run that read it and a
    later run would quietly benchmark content the course no longer has. The
    run records the block, so a task need carry only one of the two.

    Two things it does not promise. Workers take their first task at
    different moments, so a republish during a run still reaches whichever
    have not read yet; and an eviction past ``CACHED_BENCHMARKS`` runs makes
    a worker re-read. Neither is labelled — a silent re-read shows up only as
    arms measured against different text.

    ``lru_cache`` does not cache exceptions, so an unreadable block is
    retried rather than remembered, at one attempt per remaining task.
    """
    try:
        block_id = TranslationBenchmark.objects.values_list(
            "benchmark_block_id", flat=True
        ).get(pk=run_id)
    except TranslationBenchmark.DoesNotExist as error:
        # Django's own message names neither the run nor the model usefully,
        # and this failure would otherwise be recorded as the judge's.
        msg = f"Run {run_id} has no row; it was deleted."
        raise BenchmarkError(msg) from error
    return read_benchmark(block_id)


@_benchmark_task("benchmark_translate_task")
def benchmark_translate_task(_self, candidate_id, translator, target_language, run_id):
    """
    Translate the benchmark block and store it on the translator's source row.

    That row is what every validator arm is built from; the command deletes
    it once they have been, so it is never a candidate itself.

    Returns a status dict rather than raising, so one translator failing is
    data the command aggregates rather than an exception that ends the stage.
    """

    # Scoped to the run so a hand-built or mis-paired call cannot reach
    # another run's row. Dispatch always pairs the two, and a redelivered
    # task carries its own run, so this is not what stops a replay.
    candidate = TranslationBenchmarkCandidate.objects.get(
        pk=candidate_id, run_id=run_id
    )
    # Outside the handler: a bad benchmark is the run's problem, not this
    # arm's, and recording it on the row would blame the translator for it
    # once per candidate.
    benchmark = cached_benchmark(run_id)
    try:
        provider = get_translation_provider(*translator.split("/", 1))
        translated = provider.translate_text(
            benchmark.content, target_language, tag_handling=BENCHMARK_TAG_HANDLING
        )
        # translate_text hands back the source when parsing or reinsertion
        # fails, so an unchanged document means the translation did not happen.
        if not translated:
            msg = "provider returned nothing"
            raise RuntimeError(msg)  # noqa: TRY301
        translated_units, _ = units_and_elements(translated)
        if not translated_units:
            msg = f"provider returned no translatable units ({len(translated)} chars)"
            raise RuntimeError(msg)  # noqa: TRY301
        # Compared per unit, not byte for byte. translate_text keeps the
        # original unit when a batch reply arrives without its :::N:::
        # markers, then reserializes — which drops the header comment outside
        # the root — so a wholly untranslated document differs from the source
        # anyway and a byte comparison misses it. Requiring *every* unit to be
        # unchanged is what keeps the units that read identically in any
        # language — a formula or a bare comma — from failing a real arm.
        if all(unit.strip() in benchmark.units for unit in translated_units):
            msg = (
                "provider returned the source unchanged "
                f"(all {len(translated_units)} units)"
            )
            raise RuntimeError(msg)  # noqa: TRY301
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as error:  # noqa: BLE001
        candidate.error = _log_benchmark_failure(error, f"translate {translator}")
        candidate.save(update_fields=["error"])
        return {
            "status": "error",
            "candidate_id": candidate_id,
            "error": candidate.error,
        }

    candidate.translated_content = translated
    candidate.error = ""
    candidate.save(update_fields=["translated_content", "error"])
    return {"status": "success", "candidate_id": candidate_id}


@_benchmark_task("benchmark_validate_task")
def benchmark_validate_task(
    _self, candidate_id, source_candidate_id, validator, target_language, run_id
):
    """Review one translation and store the result as its own arm."""

    candidate = TranslationBenchmarkCandidate.objects.get(
        pk=candidate_id, run_id=run_id
    )
    source_arm = TranslationBenchmarkCandidate.objects.get(
        pk=source_candidate_id, run_id=run_id
    )
    benchmark = cached_benchmark(run_id)
    try:
        provider = get_translation_provider(*validator.split("/", 1))
        reviewed = provider.validate_translation(
            source_language=ENGLISH_LANGUAGE_CODE,
            target_language=target_language,
            source_content=benchmark.content,
            translated_content=source_arm.translated_content,
            timeout=BENCHMARK_VALIDATION_TIMEOUT,
            max_retries=NO_CLIENT_RETRIES,
        )
        # Validation sends whole markup and bypasses the DOM-aware path, so it
        # can return prose or restructured markup. Production applies the same
        # looks_like_markup gate but falls back to the unvalidated translation;
        # here the arm is dropped instead, so nothing unusable is scored.
        if not looks_like_markup(reviewed):
            msg = "validator returned no markup"
            raise RuntimeError(msg)  # noqa: TRY301
        _, before_elements = units_and_elements(source_arm.translated_content)
        _, after_elements = units_and_elements(reviewed)
        if after_elements != before_elements:
            msg = (
                f"validator changed the markup structure "
                f"({before_elements} elements in, {after_elements} out)"
            )
            raise RuntimeError(msg)  # noqa: TRY301
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as error:  # noqa: BLE001
        candidate.error = _log_benchmark_failure(error, f"validate {validator}")
        candidate.save(update_fields=["error"])
        return {
            "status": "error",
            "candidate_id": candidate_id,
            "error": candidate.error,
        }

    candidate.translated_content = reviewed
    candidate.error = ""
    candidate.save(update_fields=["translated_content", "error"])
    return {"status": "success", "candidate_id": candidate_id}


@_benchmark_task("benchmark_score_task")
def benchmark_score_task(_self, candidate_id, judge, target_language, run_id):
    """
    Score one candidate with one judge.

    Deliberately does not write: whether this judge counts at all is a decision
    over every result in the stage, which only the command can make.
    """

    benchmark = cached_benchmark(run_id)
    try:
        candidate = TranslationBenchmarkCandidate.objects.get(
            pk=candidate_id, run_id=run_id
        )
        rating = get_translation_provider(*judge.split("/", 1)).rate_translation(
            source_language=ENGLISH_LANGUAGE_CODE,
            target_language=target_language,
            source_content=benchmark.content,
            translated_content=candidate.translated_content,
        )
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as error:  # noqa: BLE001
        return {
            "status": "error",
            "candidate_id": candidate_id,
            "error": _log_benchmark_failure(error, f"score {judge}"),
        }
    return {
        "status": "success",
        "candidate_id": candidate_id,
        "scores": rating.scores,
        "justification": rating.justification,
    }


@_benchmark_task("benchmark_rank_task")
def benchmark_rank_task(_self, judge, label_map, target_language, run_id):
    """Rank the shortlist for one judge; ``label_map`` is label -> candidate id."""

    benchmark = cached_benchmark(run_id)
    try:
        rows = TranslationBenchmarkCandidate.objects.filter(run_id=run_id).in_bulk(
            label_map.values()
        )
        missing = sorted(set(label_map.values()) - rows.keys())
        if missing:
            # Named rather than left to KeyError, which reports one id, with
            # a traceback, as though the code were at fault.
            msg = f"candidates {missing} are not in run {run_id}"
            raise RuntimeError(msg)  # noqa: TRY301
        payload = {
            label: rows[candidate_id].translated_content
            for label, candidate_id in label_map.items()
        }
        ranks = get_translation_provider(*judge.split("/", 1)).rank_translations(
            source_language=ENGLISH_LANGUAGE_CODE,
            target_language=target_language,
            source_content=benchmark.content,
            candidates=payload,
        )
    except TRANSIENT_PROVIDER_ERRORS:
        raise
    except Exception as error:  # noqa: BLE001
        return {
            "status": "error",
            "error": _log_benchmark_failure(error, f"rank {judge}"),
        }
    return {
        "status": "success",
        "ranks": {label_map[label]: position for label, position in ranks.items()},
    }
