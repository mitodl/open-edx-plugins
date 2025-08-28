"""Tests for the DisableMathJaxForOLChatBlock filter."""
import unittest
from unittest.mock import Mock

from ol_openedx_chat_xblock.filters import DisableMathJaxForOLChatBlock

class TestDisableMathJaxForOLChatBlock(unittest.TestCase):
    """Test cases for DisableMathJaxForOLChatBlock filter."""

    def setUp(self):
        """Set up test fixtures."""
        self.filter = DisableMathJaxForOLChatBlock({}, {})

    def test_disables_mathjax_when_ol_chat_block_present(self):
        """Test that MathJax is disabled when ol_openedx_chat_xblock is present."""
        # Mock child block with ol_openedx_chat_xblock type
        mock_child = Mock()
        mock_child.block_type = "ol_openedx_chat_xblock"

        mock_block = Mock()
        mock_block.children = [mock_child]
        context = {"block": mock_block, "load_mathjax": True}
        student_view_context = {}
        result = self.filter.run_filter(context, student_view_context)
        result = self.filter.run_filter(context, student_view_context)
        assert not result["load_mathjax"]

    def test_leaves_mathjax_unchanged_when_no_ol_chat_block(self):
        """Test that MathJax setting is unchanged when no ol_openedx_chat_xblock is present."""
        # Mock child block with different type
        mock_child = Mock()
        mock_child.block_type = "some_other_block"

        # Mock parent block with children
        mock_block = Mock()
        mock_block.children = [mock_child]

        context = {"block": mock_block, "load_mathjax": True}
        student_view_context = {}

        result = self.filter.run_filter(context, student_view_context)
        result = self.filter.run_filter(context, student_view_context)

        assert result["load_mathjax"]

    def test_handles_multiple_children_with_ol_chat_block(self):
        """Test behavior with multiple children where one is ol_openedx_chat_xblock."""
        # Mock multiple child blocks
        mock_child1 = Mock()
        mock_child1.block_type = "other_block"

        mock_child2 = Mock()
        mock_child2.block_type = "ol_openedx_chat_xblock"

        mock_child3 = Mock()
        mock_child3.block_type = "another_block"

        # Mock parent block with children
        mock_block = Mock()
        mock_block.children = [mock_child1, mock_child2, mock_child3]

        context = {"block": mock_block, "load_mathjax": True}
        student_view_context = {}

        result = self.filter.run_filter(context, student_view_context)

        assert not result["load_mathjax"]

    def test_handles_empty_children_list(self):
        """Test behavior when block has no children."""
        # Mock parent block with no children
        mock_block = Mock()
        mock_block.children = []

        context = {"block": mock_block, "load_mathjax": True}
        student_view_context = {}

        result = self.filter.run_filter(context, student_view_context)

        assert result["load_mathjax"]

    def test_context_modification_in_place(self):
        """Test that the original context dictionary is modified."""
        # Mock child block with ol_openedx_chat_xblock type
        mock_child = Mock()
        mock_child.block_type = "ol_openedx_chat_xblock"

        # Mock parent block with children
        mock_block = Mock()
        mock_block.children = [mock_child]

        context = {"block": mock_block, "load_mathjax": True}
        student_view_context = {}
        result = self.filter.run_filter(context, student_view_context)

        assert result is context
        assert not context["load_mathjax"]
