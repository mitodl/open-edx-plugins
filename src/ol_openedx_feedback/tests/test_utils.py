"""Tests for block applicability and visible-title helpers."""

from types import SimpleNamespace

import pytest
from django.test import override_settings
from django.utils.translation import gettext_lazy
from ol_openedx_feedback.constants import (
    DEFAULT_VISIBLE_TITLE_FIELDS,
    TITLE_VISIBILITY_TOGGLES,
)
from ol_openedx_feedback.utils import get_visible_title, is_aside_applicable_to_block


def _block(category, **fields):
    return SimpleNamespace(category=category, **fields)


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


DISPLAY_NAME_CATEGORIES = [
    "annotatable",
    "edx_sga",
    "lti",
    "lti_consumer",
    "pdf",
    "poll",
    "problem",
    "staffgradedxblock",
    "video",
    "videoalpha",
    "word_cloud",
]


@pytest.mark.parametrize("category", DISPLAY_NAME_CATEGORIES)
def test_visible_title_returned_for_blocks_that_render_it(category):
    """Types that draw a heading on the page report their display_name."""
    block = _block(category, display_name="Lecture 1: Limits")
    assert get_visible_title(block) == "Lecture 1: Limits"


def test_every_curated_display_name_entry_is_exercised():
    """A new map entry that no test covers would ship unverified."""
    curated = {
        category
        for category, field in DEFAULT_VISIBLE_TITLE_FIELDS.items()
        if field == "display_name" and category not in TITLE_VISIBILITY_TOGGLES
    }
    assert set(DISPLAY_NAME_CATEGORIES) == curated


@pytest.mark.parametrize(
    "category",
    ["html", "poll_question", "scorm", "done", "google-document", "image"],
)
def test_no_visible_title_for_blocks_that_never_render_one(category):
    """display_name stays a Studio-only label for these."""
    block = _block(category, display_name="Wk3 intro copy - REVISED, do not reuse")
    assert get_visible_title(block) == ""


def test_unknown_block_type_has_no_visible_title():
    """An unlisted type is assumed author-only — omitting only costs wording."""
    block = _block("ol_openedx_chat_xblock", display_name="internal note")
    assert get_visible_title(block) == ""


def test_ora_uses_its_own_title_field_not_display_name():
    """ORA renders `title`; `display_name` can drift and isn't on the page."""
    block = _block(
        "openassessment",
        title="Peer Review: Essay 2",
        display_name="ORA copy v3 DO NOT REUSE",
    )
    assert get_visible_title(block) == "Peer Review: Essay 2"


def test_survey_uses_block_name_not_display_name():
    """Survey deliberately keeps display_name for Studio and renders block_name."""
    block = _block(
        "survey",
        block_name="End of Week Check-in",
        display_name="survey draft - unused",
    )
    assert get_visible_title(block) == "End of Week Check-in"


def test_drag_and_drop_title_hidden_when_author_turns_it_off():
    """show_title is author-controlled, so the name isn't always on the page."""
    shown = _block("drag-and-drop-v2", display_name="Sort the steps", show_title=True)
    hidden = _block("drag-and-drop-v2", display_name="Sort the steps", show_title=False)
    assert get_visible_title(shown) == "Sort the steps"
    assert get_visible_title(hidden) == ""


def test_missing_toggle_is_treated_as_hidden():
    """A runtime without the toggle field can't confirm it renders — don't leak."""
    block = _block("drag-and-drop-v2", display_name="Sort the steps")
    assert get_visible_title(block) == ""


def test_lazy_translation_title_is_resolved():
    """XBlock defaults are often lazy proxies, not plain strings."""
    block = _block("problem", display_name=gettext_lazy("Blank Problem"))
    assert get_visible_title(block) == "Blank Problem"


def test_non_string_title_does_not_break_block_rendering():
    """Most mapped blocks are third-party and can redefine a field in any
    release. This runs inside student_view_aside, so it must not raise."""
    assert get_visible_title(_block("problem", display_name=1.0)) == ""


def test_discussion_is_not_treated_as_having_a_visible_title():
    """It renders an empty fragment off the LEGACY provider, so the name may
    be on no page at all."""
    block = _block("discussion", display_name="Week 3 discussion")
    assert get_visible_title(block) == ""


def test_blank_and_missing_titles_degrade_to_empty():
    """A missing or whitespace-only name falls back to block-type wording."""
    assert get_visible_title(_block("video", display_name=None)) == ""
    assert get_visible_title(_block("video", display_name="   ")) == ""
    assert get_visible_title(_block("video")) == ""
