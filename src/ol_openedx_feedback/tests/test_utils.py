"""Tests for block applicability helper."""

from types import SimpleNamespace

import pytest
from django.test import override_settings
from ol_openedx_feedback.utils import is_aside_applicable_to_block


def _block(category):
    return SimpleNamespace(category=category)


@pytest.mark.parametrize(
    ("category", "expected"),
    [
        ("video", True),
        ("problem", True),
        ("html", True),
        ("vertical", False),
        ("sequential", False),
        ("chapter", False),
        ("course", False),
        (None, False),
    ],
)
def test_is_aside_applicable_to_block(category, expected):
    """Applies to leaf blocks; excludes structural containers and missing types."""
    assert is_aside_applicable_to_block(_block(category)) is expected


@override_settings(
    OL_OPENEDX_FEEDBACK_EXCLUDED_BLOCK_TYPES={
        "course",
        "chapter",
        "sequential",
        "vertical",
        "html",
    }
)
def test_excluded_block_types_setting_override():
    """A deployment can exclude an extra block type via the setting."""
    assert is_aside_applicable_to_block(_block("html")) is False
    assert is_aside_applicable_to_block(_block("video")) is True
