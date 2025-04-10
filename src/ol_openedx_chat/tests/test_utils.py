"""Tests for the util methods"""

from unittest.mock import patch

from ddt import data, ddt, unpack
from ol_openedx_chat.utils import (
    is_aside_applicable_to_block,
    is_ol_chat_enabled_for_course,
)
from tests.utils import OLChatTestCase


@ddt
class OLChatUtilTests(OLChatTestCase):
    @data(
        *[
            ("problem", True, True, True),
            ("problem", True, False, False),
            ("problem", False, True, True),
            ("problem", False, False, False),
            ("video", True, True, True),
            ("video", True, False, True),
            ("video", False, True, False),
            ("video", False, False, False),
        ]
    )
    @unpack
    def test_is_ol_chat_enabled_for_course(
        self,
        block_category,
        video_block_setting,
        problem_block_setting,
        expected_is_enabled,
    ):
        """
        Test the is_ol_chat_enabled_for_course function
        """
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            self.course.other_course_settings = {
                "OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED": video_block_setting,
                "OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED": problem_block_setting,
            }
            mock_get_course_by_id.return_value = self.course
            block = (
                self.problem_block if block_category == "problem" else self.video_block
            )
            assert is_ol_chat_enabled_for_course(block) == expected_is_enabled

    @data("problem", "video")
    def test_is_ol_chat_enabled_for_course_when_no_course_found(self, block_category):
        """
        Test the `is_ol_chat_enabled_for_course` function when `get_course_by_id` fails
        """
        with patch("ol_openedx_chat.utils.get_course_by_id") as mock_get_course_by_id:
            mock_get_course_by_id.side_effect = Exception()
            block = (
                self.problem_block if block_category == "problem" else self.video_block
            )
            assert is_ol_chat_enabled_for_course(block)

    @data(
        *[
            ("problem", True),
            ("video", True),
            ("html", False),
        ]
    )
    @unpack
    def test_is_aside_applicable_to_block(self, block_category, is_aside_applicable):
        """Tests that `is_aside_applicable_to_block` returns the expected value"""
        if block_category == "problem":
            block = self.problem_block
        elif block_category == "video":
            block = self.video_block
        elif block_category == "html":
            block = self.html_block
        assert is_aside_applicable_to_block(block) == is_aside_applicable
