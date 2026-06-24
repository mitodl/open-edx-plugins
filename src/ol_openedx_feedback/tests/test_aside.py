"""Tests for the FeedbackAside trigger rendering and gating."""

from types import SimpleNamespace
from unittest import mock

from ol_openedx_feedback.block import FeedbackAside


def _aside(user_id, *, is_author=False):
    aside = FeedbackAside(scope_ids=mock.MagicMock(), runtime=mock.MagicMock())
    aside.runtime.user_id = user_id
    aside.runtime.is_author_mode = is_author
    return aside


def _block():
    block = SimpleNamespace()
    block.usage_key = mock.MagicMock()
    block.usage_key.block_id = "abc"
    block.usage_key.course_key = "course-v1:MITx+6.00+2024"
    block.category = "video"
    block.display_name = "Lecture 1"
    return block


def test_no_trigger_for_anonymous_user():
    fragment = _aside(user_id=None).student_view_aside(_block())
    assert fragment.content == ""


def test_no_trigger_in_author_mode():
    fragment = _aside(user_id=5, is_author=True).student_view_aside(_block())
    assert fragment.content == ""


def test_trigger_rendered_for_authenticated_learner():
    fragment = _aside(user_id=5).student_view_aside(_block())
    assert "ol-feedback-trigger-abc" in fragment.content
    assert "ol-feedback-panel" not in fragment.content
