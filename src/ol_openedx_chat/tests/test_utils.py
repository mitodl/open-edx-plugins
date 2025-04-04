"""Tests for the util methods"""

from unittest.mock import patch

from ddt import data, ddt, unpack
from ol_openedx_chat.tests.utils import OLChatTestCase
from ol_openedx_chat.utils import (
    is_aside_applicable_to_block,
    is_ol_chat_enabled_for_course,
)


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
        """Tests that `is_ol_chat_enabled_for_course` returns the expected value"""
        with patch(
            "ol_openedx_chat.utils.get_course_by_id", new=self.course
        ) as mock_get_course_by_id:
            mock_get_course_by_id.return_value.other_course_settings = {
                "OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED": video_block_setting,
                "OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED": problem_block_setting,
            }
            block = (
                self.problem_block if block_category == "problem" else self.video_block
            )
            assert is_ol_chat_enabled_for_course(block) == expected_is_enabled

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
        block = self.problem_block if block_category == "problem" else self.video_block
        assert is_aside_applicable_to_block(block) == is_aside_applicable
