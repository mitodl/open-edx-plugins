# ruff: noqa: E501
"""Utility methods for the AI chat"""

from lms.djangoapps.courseware.courses import get_course_by_id
from ol_openedx_chat.constants import BLOCK_TYPE_TO_SETTINGS, CHAT_APPLICABLE_BLOCKS


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
    course = get_course_by_id(block.usage_key.course_key)
    other_course_settings = course.other_course_settings
    block_type = getattr(block, "category", None)
    return other_course_settings.get(BLOCK_TYPE_TO_SETTINGS.get(block_type))
