"""
Utility functions for working with Blocks API responses in the Course Outline API.
"""

from ol_openedx_course_outline_api.constants import (
    CONTAINER_TYPES,
    KNOWN_LEAF_TYPES,
    NOT_GRADED_FORMAT,
    VISIBLE_TO_STAFF_ONLY_KEYS,
)


def is_visible_to_staff_only(block):
    """
    Return True if the block is staff-only, based on any known visibility key.
    """
    return any(block.get(key) is True for key in VISIBLE_TO_STAFF_ONLY_KEYS)


def iter_descendant_ids(blocks_data, root_id):
    """
    Yield all descendant block ids (including root_id) from blocks_data.

    Implemented iteratively to avoid recursion depth issues on very large courses.
    """
    seen = set()
    stack = [root_id]
    while stack:
        block_id = stack.pop()
        if block_id in seen:
            continue
        seen.add(block_id)
        yield block_id
        children = blocks_data.get(block_id, {}).get("children") or []
        stack.extend(children)


def is_graded_sequential(block):
    """
    Return True if this block is a sequential that counts as an assignment.

    The Blocks API returns the block's raw `graded` field (default False).
    Studio can show a subsection as "linked" to an assignment type (format)
    while the block still has graded=False. We treat a sequential as an
    assignment if graded is True OR if it has a non-empty assignment format
    (e.g. Homework, Lab, Midterm Exam, Final Exam, or custom names).
    """
    if block.get("type") != "sequential":
        return False
    if block.get("graded") is True:
        return True
    format_val = (block.get("format") or "").strip()
    return bool(format_val) and format_val.lower() != NOT_GRADED_FORMAT.lower()


def count_blocks_by_type_under_chapter(blocks_data, chapter_id, block_type):
    """
    Count blocks of the given type under the chapter (excludes staff-only).
    """
    count = 0
    for block_id in iter_descendant_ids(blocks_data, chapter_id):
        block = blocks_data.get(block_id, {})
        if is_visible_to_staff_only(block):
            continue
        if block.get("type") == block_type:
            count += 1
    return count


def count_assignments_under_chapter(blocks_data, chapter_id):
    """
    Count sequential blocks that are graded or have an assignment format
    (excludes staff-only).
    """
    count = 0
    for block_id in iter_descendant_ids(blocks_data, chapter_id):
        block = blocks_data.get(block_id, {})
        if is_visible_to_staff_only(block):
            continue
        if is_graded_sequential(block):
            count += 1
    return count


def count_app_items_under_chapter(blocks_data, chapter_id):
    """
    Count leaf blocks that are not video, html, or problem (custom/app items;
    excludes staff-only).
    """
    count = 0
    for block_id in iter_descendant_ids(blocks_data, chapter_id):
        block = blocks_data.get(block_id, {})
        if is_visible_to_staff_only(block):
            continue
        block_type = block.get("type") or ""
        children = block.get("children") or []
        is_leaf = len(children) == 0
        if (
            is_leaf
            and block_type not in CONTAINER_TYPES
            and block_type not in KNOWN_LEAF_TYPES
        ):
            count += 1
    return count


def build_modules_from_blocks(blocks_data, root_id):
    """
    Build list of module dicts (one per chapter) from get_blocks response.
    """
    modules = []
    root_block = blocks_data.get(root_id, {})
    for child_id in root_block.get("children") or []:
        block = blocks_data.get(child_id, {})
        if block.get("type") != "chapter":
            continue
        if is_visible_to_staff_only(block):
            continue

        counts = {
            "videos": count_blocks_by_type_under_chapter(
                blocks_data, child_id, "video"
            ),
            "readings": count_blocks_by_type_under_chapter(
                blocks_data, child_id, "html"
            ),
            "problems": count_blocks_by_type_under_chapter(
                blocks_data, child_id, "problem"
            ),
            "assignments": count_assignments_under_chapter(blocks_data, child_id),
            "app_items": count_app_items_under_chapter(blocks_data, child_id),
        }
        module = {
            "id": child_id,
            "title": block.get("display_name") or "",
            "effort_time": block.get("effort_time") or 0,
            "effort_activities": block.get("effort_activities") or 0,
            "counts": counts,
        }
        modules.append(module)
    return modules
