"""
Orchestration service for short-video course generation.

This module is the single callable used by both the management command and
(future) admin actions. It is intentionally free of Django ORM writes so
callers can persist results using whichever model suits them.
"""

import logging
import time
from dataclasses import dataclass, field

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils import (
    CourseGroups,
    CreationStats,
    CsvRow,
    build_course_structure,
    create_course,
    group_rows,
    parse_csv,
)

log = logging.getLogger(__name__)


@dataclass
class CourseRunResult:
    """Outcome for one course (one unique course_key) within a batch."""

    course_key_str: str
    course_name: str
    success: bool
    error: str = ""
    stats: CreationStats | None = None


@dataclass
class BatchResult:
    """Aggregated outcome for one CSV run."""

    success: bool
    validation_errors: list[str] = field(default_factory=list)
    run_results: list[CourseRunResult] = field(default_factory=list)
    dry_run: bool = False
    # dry_run only: planned structure per course_key
    planned_ops: dict[str, dict] = field(default_factory=dict)
    duration_seconds: float = 0.0


def generate_custom_courses(
    csv_path: str,
    user_id: int,
    *,
    dry_run: bool = False,
) -> BatchResult:
    """
    Parse *csv_path*, validate, then create each course described in the CSV.

    Each unique ``course_key`` column value produces one new course.
    The course hierarchy (sections → subsections → units → video blocks) is
    built from the grouped rows for that course.

    In dry-run mode the function performs CSV parsing and validation only,
    returning a plan of intended operations without writing to the modulestore.
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

    # --- Validate course keys ---
    validation_errors: list[str] = []
    for row in rows:
        try:
            CourseKey.from_string(row.course_key_str)
        except InvalidKeyError:
            validation_errors.append(
                f"Line {row.line_number}: invalid course key '{row.course_key_str}'"
            )

    if validation_errors:
        return BatchResult(
            success=False,
            validation_errors=validation_errors,
            duration_seconds=time.monotonic() - start,
        )

    groups: CourseGroups = group_rows(rows)

    # --- Dry-run: return plan, no writes ---
    if dry_run:
        planned: dict[str, dict] = {}
        for course_key_str, course_rows in groups.items():
            sections: dict[str, set[str]] = {}
            for row in course_rows:
                sections.setdefault(row.section_name, set()).add(row.subsection_name)
            planned[course_key_str] = {
                "course_name": course_rows[0].course_name,
                "sections": {sec: sorted(subs) for sec, subs in sections.items()},
                "total_units": len(course_rows),
            }
        return BatchResult(
            success=True,
            dry_run=True,
            planned_ops=planned,
            duration_seconds=time.monotonic() - start,
        )

    # --- Live run: create each course ---
    run_results: list[CourseRunResult] = []
    overall_success = True

    for course_key_str, course_rows in groups.items():
        course_name = course_rows[0].course_name
        run_result = CourseRunResult(
            course_key_str=course_key_str,
            course_name=course_name,
            success=False,
        )

        try:
            course_key = CourseKey.from_string(course_key_str)
            create_course(course_key, course_name, user_id)
            stats = build_course_structure(course_key, course_rows, user_id)
            run_result.success = True
            run_result.stats = stats
        except (ValueError, RuntimeError) as exc:
            log.exception("Failed to create course %s", course_key_str)
            run_result.error = str(exc)
            overall_success = False

        run_results.append(run_result)

    return BatchResult(
        success=overall_success,
        run_results=run_results,
        duration_seconds=time.monotonic() - start,
    )
