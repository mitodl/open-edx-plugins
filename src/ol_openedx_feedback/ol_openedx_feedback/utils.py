"""Utility helpers for ol_openedx_feedback."""

from django.conf import settings
from django.utils.functional import Promise

from ol_openedx_feedback.constants import (
    DEFAULT_EXCLUDED_BLOCK_TYPES,
    DEFAULT_VISIBLE_TITLE_FIELDS,
    TITLE_VISIBILITY_TOGGLES,
)


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


def get_visible_title(block):
    """Return the title the learner can see on the page, or "" if there is none.

    "" tells the panel to name the block type instead.
    """
    block_type = getattr(block, "category", None)
    title_field = DEFAULT_VISIBLE_TITLE_FIELDS.get(block_type)
    if not title_field:
        return ""

    toggle_field = TITLE_VISIBILITY_TOGGLES.get(block_type)
    if toggle_field and not getattr(block, toggle_field, False):
        return ""

    title = getattr(block, title_field, "")
    if not isinstance(title, str | Promise):
        return ""
    return str(title).strip()
