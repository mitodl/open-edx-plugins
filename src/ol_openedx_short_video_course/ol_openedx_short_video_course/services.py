"""
Orchestration service for short-video course generation.

This module is the single callable used by both management commands and
(future) admin actions. It is intentionally free of Django ORM writes so
callers can persist results using whichever model suits them.
"""

import logging
import time
from dataclasses import dataclass, field

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils.course_builder import prepare_destination
from ol_openedx_short_video_course.utils.course_transformer import (
    TransformResult,
    apply_group_actions,
)
from ol_openedx_short_video_course.utils.course_validator import validate_all_groups
from ol_openedx_short_video_course.utils.csv_parser import (
    CsvRow,
    derive_dest_course_key,
    group_rows,
    parse_csv,
)
from ol_openedx_short_video_course.utils.val_validator import validate_video_ids

log = logging.getLogger(__name__)


@dataclass
class RunResult:
    """Outcome for a single (source, type, industry) variant."""

    source_course_key: str
    dest_course_key: str
    type_code: str
    industry_code: str
    success: bool
    error: str = ""
    transform_result: TransformResult | None = None


@dataclass
class BatchResult:
    """Aggregated outcome for one CSV run."""

    success: bool
    validation_errors: list[str] = field(default_factory=list)
    run_results: list[RunResult] = field(default_factory=list)
    dry_run: bool = False
    # dry_run only: planned operations per destination key
    planned_ops: dict[str, dict] = field(default_factory=dict)
    duration_seconds: float = 0.0


def generate_custom_courses(  # noqa: C901
    csv_path: str,
    user_id: int,
    *,
    dry_run: bool = False,
    treat_industry_code_O_as_original: bool = False,
) -> BatchResult:
    """
    Parse *csv_path*, validate all groups, then create destination courses.

    Validation is all-or-nothing: if any group has an error, no courses are
    created and a BatchResult with ``success=False`` is returned.

    In dry-run mode the function performs full validation and returns a plan
    of intended operations without writing anything to the modulestore.
    """
    start = time.monotonic()

    # --- Parse ---
    try:
        rows: list[CsvRow] = parse_csv(csv_path)
    except (FileNotFoundError, ValueError) as exc:
        return BatchResult(
            success=False,
            validation_errors=[str(exc)],
            duration_seconds=time.monotonic() - start,
        )

    groups = group_rows(rows)

    # --- VAL video ID pre-validation ---
    update_video_ids: set[str] = {
        row.video_id
        for row_list in groups.values()
        for row in row_list
        if row.action == "update"
    }
    if update_video_ids:
        val_results = validate_video_ids(update_video_ids)
        invalid_ids = [vid for vid, valid in val_results.items() if not valid]
        if invalid_ids:
            return BatchResult(
                success=False,
                validation_errors=[
                    f"Invalid VAL video IDs (not found in edx-val): "
                    f"{', '.join(sorted(invalid_ids))}"
                ],
                duration_seconds=time.monotonic() - start,
            )

    # --- Structural pre-flight validation (all groups) ---
    report = validate_all_groups(groups)
    if not report.is_valid:
        return BatchResult(
            success=False,
            validation_errors=report.errors,
            duration_seconds=time.monotonic() - start,
        )

    # --- Dry-run: return plan, no writes ---
    if dry_run:
        planned: dict[str, dict] = {}
        for (src_str, type_code, industry_code), group_row_list in groups.items():
            src_key = CourseKey.from_string(src_str)
            if treat_industry_code_O_as_original and industry_code == "O":
                dest_key = CourseKey(
                    org=src_key.org,
                    course=f"{src_key.course}.{type_code}",
                    run=src_key.run,
                )
            else:
                dest_key = derive_dest_course_key(src_key, type_code, industry_code)
            planned[str(dest_key)] = {
                "source": src_str,
                "type": type_code,
                "industry": industry_code,
                "actions": {
                    "keep": sum(1 for r in group_row_list if r.action == "keep"),
                    "remove": sum(1 for r in group_row_list if r.action == "remove"),
                    "update": sum(1 for r in group_row_list if r.action == "update"),
                },
            }
        return BatchResult(
            success=True,
            dry_run=True,
            planned_ops=planned,
            duration_seconds=time.monotonic() - start,
        )

    # --- Live run: process each group sequentially ---
    run_results: list[RunResult] = []
    overall_success = True

    for (src_str, type_code, industry_code), group_row_list in groups.items():
        src_key = CourseKey.from_string(src_str)
        if treat_industry_code_O_as_original and industry_code == "O":
            dest_key = CourseKey(
                org=src_key.org,
                course=f"{src_key.course}.{type_code}",
                run=src_key.run,
            )
        else:
            dest_key = derive_dest_course_key(src_key, type_code, industry_code)

        run_result = RunResult(
            source_course_key=src_str,
            dest_course_key=str(dest_key),
            type_code=type_code,
            industry_code=industry_code,
            success=False,
        )

        try:
            prepare_destination(src_key, dest_key, user_id)
            transform_result = apply_group_actions(dest_key, group_row_list, user_id)
            run_result.success = True
            run_result.transform_result = transform_result
            log.info(
                "Generated %s: kept=%d removed=%d updated=%d",
                dest_key,
                transform_result.kept,
                transform_result.removed,
                transform_result.updated,
            )
        except (InvalidKeyError, ValueError, RuntimeError) as exc:
            log.exception("Failed to generate %s → %s", src_str, dest_key)
            run_result.error = str(exc)
            overall_success = False

        run_results.append(run_result)

    return BatchResult(
        success=overall_success,
        run_results=run_results,
        duration_seconds=time.monotonic() - start,
    )
