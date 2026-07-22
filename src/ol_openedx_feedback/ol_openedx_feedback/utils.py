"""Utility helpers for ol_openedx_feedback."""

from django.conf import settings

from ol_openedx_feedback.constants import DEFAULT_EXCLUDED_BLOCK_TYPES


def get_excluded_block_types():
    """Return the block types that never get a feedback trigger.

    Defaults to structural containers; overridable per deployment via the
    ``OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES`` setting.
    """
    return set(
        getattr(
            settings,
            "OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES",
            DEFAULT_EXCLUDED_BLOCK_TYPES,
        )
    )


def is_aside_applicable_to_block(block):
    """Feedback applies to every block type except excluded containers."""
    block_type = getattr(block, "category", None)
    return bool(block_type) and block_type not in get_excluded_block_types()
