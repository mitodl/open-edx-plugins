"""Tests for the util methods"""

from unittest.mock import Mock, patch

import pytest
from ol_openedx_chat.utils import (
    is_aside_applicable_to_block,
    is_ol_chat_enabled_for_course,
)


@pytest.mark.parametrize(
    ("block_category", "is_aside_applicable"),
    [
        ("problem", True),
        ("video", True),
        ("html", False),
    ],
)
def test_is_aside_applicable_to_block(block_category, is_aside_applicable):
    """Tests that `is_aside_applicable_to_block` returns the expected value"""
    assert (
        is_aside_applicable_to_block(Mock(category=block_category))
        == is_aside_applicable
    )


@pytest.mark.parametrize(
    (
        "block_category",
        "video_block_setting",
        "problem_block_setting",
        "expected_is_enabled",
    ),
    [
        ("problem", True, True, True),
        ("problem", True, False, False),
        ("problem", False, True, True),
        ("problem", False, False, False),
        ("video", True, True, True),
        ("video", True, False, True),
        ("video", False, True, False),
        ("video", False, False, False),
    ],
)
def test_is_ol_chat_enabled_for_course(
    block_category, video_block_setting, problem_block_setting, expected_is_enabled
):
    """Tests that `is_ol_chat_enabled_for_course` returns the expected value"""
    with patch(
        "ol_openedx_chat.utils.get_course_by_id", new=Mock()
    ) as mock_get_course_by_id:
        mock_get_course_by_id.return_value.other_course_settings = {
            "OL_OPENEDX_CHAT_VIDEO_BLOCK_ENABLED": video_block_setting,
            "OL_OPENEDX_CHAT_PROBLEM_BLOCK_ENABLED": problem_block_setting,
        }
        assert (
            is_ol_chat_enabled_for_course(Mock(category=block_category))
            == expected_is_enabled
        )
