"""Tests for feedback serializers."""

from ol_openedx_feedback.serializers import FeedbackCreateSerializer

VALID = {
    "course_id": "course-v1:MITx+6.00+2024",
    "block_usage_key": "block-v1:MITx+6.00+2024+type@video+block@abc",
    "block_type": "video",
    "block_display_name": "Lecture 1",
    "rating": 5,
    "comment": "Great",
}


def test_create_serializer_accepts_valid_payload():
    serializer = FeedbackCreateSerializer(data=VALID)
    assert serializer.is_valid(), serializer.errors


def test_rating_out_of_range_is_rejected():
    serializer = FeedbackCreateSerializer(data={**VALID, "rating": 6})
    assert not serializer.is_valid()
    assert "rating" in serializer.errors


def test_comment_too_long_is_rejected():
    serializer = FeedbackCreateSerializer(data={**VALID, "comment": "x" * 1001})
    assert not serializer.is_valid()
    assert "comment" in serializer.errors


def test_comment_is_optional():
    payload = {k: v for k, v in VALID.items() if k != "comment"}
    serializer = FeedbackCreateSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors


def test_invalid_course_id_is_rejected():
    serializer = FeedbackCreateSerializer(data={**VALID, "course_id": "not-a-key"})
    assert not serializer.is_valid()
    assert "course_id" in serializer.errors
