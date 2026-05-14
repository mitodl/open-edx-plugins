"""Pre-flight validation of all CSV groups against source courses."""

# ruff: noqa: C901,PLR0912,PLR0915

import logging
from dataclasses import dataclass, field

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey

from ol_openedx_short_video_course.utils.csv_parser import (
    CsvRow,
    derive_dest_course_key,
    extract_block_id,
)

log = logging.getLogger(__name__)


@dataclass
class ValidationReport:
    """Collects all validation errors across all groups before returning."""

    errors: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """Return True when no validation errors were collected."""
        return len(self.errors) == 0

    def format_errors(self) -> str:
        """Format all collected errors as a readable multiline string."""
        return "\n".join(f"  • {e}" for e in self.errors)


def validate_all_groups(
    groups: dict[tuple[str, str, str], list[CsvRow]],
) -> ValidationReport:
    """
    Validate every group in the CSV against its source course.

    All errors from all groups are collected before returning so the operator
    sees the complete picture in one shot.

    Checks performed per group:
    1. Source course key is parseable and the course exists.
    2. Destination course does not already exist.
    3. No duplicate (section, subsection) pairs within the group.
    4. Every section/subsection usage key is valid and exists in the source.
    5. Every source subsection appears exactly once in the group's CSV rows.
    """
    from xmodule.modulestore.django import modulestore  # noqa: PLC0415

    report = ValidationReport()
    store = modulestore()

    # Load each unique source course once and cache the block tree.
    source_trees: dict[str, dict[str, set[str]] | None] = {}

    for source_key_str in {key_str for key_str, *_ in groups}:
        try:
            source_course_key = CourseKey.from_string(source_key_str)
        except InvalidKeyError:
            report.errors.append(f"Invalid source course key: '{source_key_str}'")
            source_trees[source_key_str] = None
            continue

        course = store.get_course(source_course_key, depth=4)
        if course is None:
            report.errors.append(
                f"Source course not found in modulestore: '{source_key_str}'"
            )
            source_trees[source_key_str] = None
        else:
            source_trees[source_key_str] = _build_course_tree(course)

    # Validate each group individually.
    for (source_key_str, type_code, industry_code), rows in groups.items():
        label = f"[source={source_key_str}, type={type_code}, industry={industry_code}]"
        tree = source_trees.get(source_key_str)

        if tree is None:
            # Source error already reported above; skip structural checks.
            continue

        # Check that destination does not already exist.
        try:
            source_key = CourseKey.from_string(source_key_str)
        except InvalidKeyError as exc:
            report.errors.append(
                f"{label}: Invalid source course key while checking destination: {exc}"
            )
            continue

        dest_key = derive_dest_course_key(source_key, type_code, industry_code)
        if store.get_course(dest_key) is not None:
            report.errors.append(
                f"{label}: Destination course already exists: '{dest_key}'. "
                "Delete it first or choose a different type/industry combination."
            )

        # Detect duplicate (section, subsection) pairs within this group.
        seen_pairs: set[tuple[str, str]] = set()
        for row in rows:
            pair = (row.section_key_str, row.subsection_key_str)
            if pair in seen_pairs:
                report.errors.append(
                    f"{label} line {row.line_number}: Duplicate row for "
                    f"section='{row.section_key_str}' "
                    f"subsection='{row.subsection_key_str}'"
                )
            seen_pairs.add(pair)

        # Build the set of (section_block_id, subsection_block_id) pairs in the CSV.
        csv_map: dict[str, set[str]] = {}
        for row in rows:
            sec_id = extract_block_id(row.section_key_str)
            sub_id = extract_block_id(row.subsection_key_str)

            if sec_id is None:
                report.errors.append(
                    f"{label} line {row.line_number}: "
                    f"Cannot parse section usage key '{row.section_key_str}'"
                )
                continue
            if sub_id is None:
                report.errors.append(
                    f"{label} line {row.line_number}: "
                    f"Cannot parse subsection usage key '{row.subsection_key_str}'"
                )
                continue

            csv_map.setdefault(sec_id, set()).add(sub_id)

        # Every CSV section must exist in the source.
        for sec_id, csv_subs in csv_map.items():
            if sec_id not in tree:
                report.errors.append(
                    f"{label}: Section block_id='{sec_id}' not found in source course"
                )
                continue
            # Every CSV subsection must exist under that section.
            for sub_id in csv_subs:
                if sub_id not in tree[sec_id]:
                    report.errors.append(
                        f"{label}: Subsection block_id='{sub_id}' not found "
                        f"under section '{sec_id}' in source course"
                    )

        # Every source subsection must appear exactly once in the CSV.
        for src_sec_id, src_subs in tree.items():
            if src_sec_id not in csv_map:
                report.errors.append(
                    f"{label}: Source section '{src_sec_id}' "
                    "is not covered by any CSV row"
                )
                continue
            for src_sub_id in src_subs:
                if src_sub_id not in csv_map[src_sec_id]:
                    report.errors.append(
                        f"{label}: Source subsection '{src_sub_id}' under section "
                        f"'{src_sec_id}' is not covered by any CSV row"
                    )

    return report


def _build_course_tree(course) -> dict[str, set[str]]:
    """
    Return {section_block_id: {subsection_block_id, ...}} for a loaded course.

    Requires the course to have been loaded with depth >= 2.
    """
    tree: dict[str, set[str]] = {}
    for section in course.get_children():
        sec_id = section.location.block_id
        tree[sec_id] = {sub.location.block_id for sub in section.get_children()}
    return tree
