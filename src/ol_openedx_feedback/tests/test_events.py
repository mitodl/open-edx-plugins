"""Tests for the feedback tracking event."""

from types import SimpleNamespace
from unittest import mock

from ol_openedx_feedback.constants import FEEDBACK_SUBMITTED_EVENT
from ol_openedx_feedback.events import emit_feedback_event
from opaque_keys.edx.keys import CourseKey, UsageKey

FEEDBACK_ID = 7
RATING = 4


def _feedback():
    return SimpleNamespace(
        id=FEEDBACK_ID,
        course_id=CourseKey.from_string("course-v1:MITx+6.00+2024"),
        block_usage_key=UsageKey.from_string(
            "block-v1:MITx+6.00+2024+type@video+block@abc"
        ),
        block_type="video",
        rating=RATING,
        comment="ok",
    )


def test_emit_feedback_event_sends_expected_payload():
    with mock.patch("ol_openedx_feedback.events.tracker") as tracker:
        emit_feedback_event(_feedback())
    tracker.emit.assert_called_once()
    name, payload = tracker.emit.call_args[0]
    assert name == FEEDBACK_SUBMITTED_EVENT
    assert payload["feedback_id"] == FEEDBACK_ID
    assert payload["rating"] == RATING
    assert payload["has_comment"] is True
    assert payload["block_type"] == "video"
