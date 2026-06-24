"""Tests for block applicability helper."""

from types import SimpleNamespace

from ol_openedx_feedback.utils import is_aside_applicable_to_block


def _block(category):
    return SimpleNamespace(category=category)


def test_leaf_blocks_are_applicable():
    assert is_aside_applicable_to_block(_block("video")) is True
    assert is_aside_applicable_to_block(_block("problem")) is True
    assert is_aside_applicable_to_block(_block("html")) is True


def test_container_blocks_are_excluded():
    assert is_aside_applicable_to_block(_block("vertical")) is False
    assert is_aside_applicable_to_block(_block("sequential")) is False
    assert is_aside_applicable_to_block(_block("chapter")) is False
    assert is_aside_applicable_to_block(_block("course")) is False


def test_missing_category_is_not_applicable():
    assert is_aside_applicable_to_block(_block(None)) is False
