"""Tests for the DisableMathJaxForOLChatBlock filter."""

import unittest
from unittest.mock import Mock

from ol_openedx_chat_xblock.filters import DisableMathJaxForOLChatBlock


class TestDisableMathJaxForOLChatBlock(unittest.TestCase):
    """Test cases for DisableMathJaxForOLChatBlock filter."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = DisableMathJaxForOLChatBlock({}, {})

    def create_block(self, block_type):
        """Helper method to create a mock chat block."""
        mock_child = Mock()
        mock_child.block_type = block_type
        return mock_child

    def test_disables_mathjax_when_ol_chat_block_present(self):
        """Test that MathJax is disabled when ol_openedx_chat_xblock is present."""
        # Mock child block with ol_openedx_chat_xblock type
        mock_block = self.create_block(block_type="parent_block")
        mock_block.children = [self.create_block(block_type="ol_openedx_chat_xblock")]
        context = {"block": mock_block, "load_mathjax": True}
        self.filter.run_filter(context, {})
        assert not context["load_mathjax"]

    def test_leaves_mathjax_unchanged_when_no_ol_chat_block(self):
        """Test that MathJax setting is unchanged when no ol_openedx_chat_xblock is
        present."""
        # Mock child block with different type
        mock_block = self.create_block(block_type="parent_block")
        mock_block.children = [self.create_block(block_type="some_other_block")]
        context = {"block": mock_block, "load_mathjax": True}
        self.filter.run_filter(context, {})
        assert context["load_mathjax"]

    def test_handles_multiple_children_with_ol_chat_block(self):
        """Test behavior with multiple children where one is ol_openedx_chat_xblock."""
        # Mock multiple child blocks
        mock_block = self.create_block(block_type="parent_block")
        mock_block.children = [self.create_block(block_type="some_other_block")]
        # Mock parent block with children
        mock_block = Mock()
        mock_block.children = [
            self.create_block(block_type="some_other_block"),
            self.create_block(block_type="ol_openedx_chat_xblock"),
            self.create_block(block_type="another_block"),
        ]
        context = {"block": mock_block, "load_mathjax": True}
        self.filter.run_filter(context, {})
        assert not context["load_mathjax"]

    def test_handles_empty_children_list(self):
        """Test behavior when block has no children."""
        # Mock parent block with no children
        mock_block = self.create_block(block_type="parent_block")
        mock_block.children = []
        context = {"block": mock_block, "load_mathjax": True}
        self.filter.run_filter(context, {})
        assert context["load_mathjax"]

    def test_context_modification_in_place(self):
        """Test that the original context dictionary is modified."""
        # Mock parent block with children
        mock_block = self.create_block(block_type="parent_block")
        mock_block.children = [self.create_block(block_type="ol_openedx_chat_xblock")]
        context = {"block": mock_block, "load_mathjax": True}
        self.filter.run_filter(context, {})
        assert not context["load_mathjax"]
