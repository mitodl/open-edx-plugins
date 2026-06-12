"""Tests for the BlockFeedback model."""

import pytest
from django.contrib.auth import get_user_model
from ol_openedx_feedback.models import BlockFeedback
from opaque_keys.edx.keys import CourseKey, UsageKey


@pytest.mark.django_db
def test_block_feedback_persists_and_stringifies():
    user = get_user_model().objects.create(username="learner")
    fb = BlockFeedback.objects.create(
        user=user,
        course_id=CourseKey.from_string("course-v1:MITx+6.00+2024"),
        course_title="Intro to CS",
        block_usage_key=UsageKey.from_string(
            "block-v1:MITx+6.00+2024+type@video+block@abc"
        ),
        block_type="video",
        block_display_name="Lecture 1",
        rating=4,
        comment="Helpful",
    )
    assert fb.pk is not None
    assert "4" in str(fb)
    assert fb.created is not None
