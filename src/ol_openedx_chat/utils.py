# ruff: noqa: E501
"""Utility methods for the AI chat"""

from lms.djangoapps.courseware.courses import get_course_by_id
from ol_openedx_chat.constants import BLOCK_TYPE_TO_SETTINGS, CHAT_APPLICABLE_BLOCKS
from opaque_keys.edx.locator import CourseLocator


def is_aside_applicable_to_block(block):
    """Check if the xBlock should support AI Chat"""
    return getattr(block, "category", None) in CHAT_APPLICABLE_BLOCKS


def is_ol_chat_enabled_for_course(block):
    """
    Return whether OL Chat is enabled or not for a block type in a course

    Args:
        block (ProblemBlock or VideoBlock): The block for which to check if OL Chat is enabled

    Returns:
        bool: True if OL Chat is enabled, False otherwise
    """
    # This is kind of a hack for course import. During course import, the course_key
    # string is in the format `{org}/{course_code}/{run_code}` and not in the format
    # `course-v1:{org}+{course_code}+{run_code}`. This results in no course found.
    if "/" in str(block.usage_key.course_key):
        course_id = str(block.usage_key.course_key)
        course_id = course_id.replace("/", "+")
        course_id = CourseLocator.from_string(f"course-v1:{course_id}")
    else:
        course_id = block.usage_key.course_key

    course = get_course_by_id(course_id)
    other_course_settings = course.other_course_settings
    block_type = getattr(block, "category", None)
    return other_course_settings.get(BLOCK_TYPE_TO_SETTINGS.get(block_type))
