"""Utility helpers for ol_openedx_feedback."""

from ol_openedx_feedback.constants import EXCLUDED_BLOCK_TYPES


def is_aside_applicable_to_block(block):
    """Feedback applies to every block type except structural containers."""
    block_type = getattr(block, "category", None)
    return bool(block_type) and block_type not in EXCLUDED_BLOCK_TYPES
