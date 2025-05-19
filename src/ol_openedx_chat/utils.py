# ruff: noqa: E501
"""Utility methods for the AI chat"""

from lms.djangoapps.courseware.courses import get_course_by_id
from opaque_keys.edx.locator import CourseLocator

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
    # During course import, the course_key uses older format `{org}/{course}/{run}`
    # as explained in `https://github.com/openedx/edx-platform/blob/8ad4d081fbdc024ed08cd1477380b395d78bb051/common/lib/xmodule/xmodule/modulestore/xml.py#L573`.
    # We convert it to the latest course key if course_id is deprecated/old format.
    course_id = block.usage_key.course_key
    if course_id.deprecated:
        course_id = CourseLocator(course_id.org, course_id.course, course_id.run)

    # Sometimes we cannot find a course by the ID i.e. during course import.
    # We return True in that case to avoid breaking the import process.
    # This will work fine with LMS and CMS.
    try:
        course = get_course_by_id(course_id)
    except Exception:  # noqa: BLE001
        return True

    other_course_settings = course.other_course_settings
    block_type = getattr(block, "category", None)
    return other_course_settings.get(BLOCK_TYPE_TO_SETTINGS.get(block_type))
