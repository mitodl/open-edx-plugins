"""Analytics event emission for ol_openedx_feedback."""

from eventtracking import tracker

from ol_openedx_feedback.constants import FEEDBACK_SUBMITTED_EVENT


def emit_feedback_event(feedback):
    """Emit a tracking event so feedback reaches the data platform."""
    tracker.emit(
        FEEDBACK_SUBMITTED_EVENT,
        {
            "feedback_id": feedback.id,
            "course_id": str(feedback.course_id),
            "block_usage_key": str(feedback.block_usage_key),
            "block_type": feedback.block_type,
            "rating": feedback.rating,
            "has_comment": bool(feedback.comment),
            "comment": feedback.comment,
        },
    )
