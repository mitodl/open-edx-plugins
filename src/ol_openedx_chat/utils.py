"""Utility methods for the AI chat"""

from ol_openedx_chat.constants import CHAT_APPLICABLE_BLOCKS


def is_aside_applicable_to_block(block):
    """Check if the xBlock should support AI Chat"""
    return getattr(block, "category", None) in CHAT_APPLICABLE_BLOCKS
