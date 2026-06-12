"""Tests for the feedback REST API (write + read)."""

import pytest
from django.contrib.auth import get_user_model
from ol_openedx_feedback.models import BlockFeedback
from rest_framework import status
from rest_framework.test import APIClient

URL = "/api/feedback/v1/submissions/"
PAYLOAD = {
    "course_id": "course-v1:MITx+6.00+2024",
    "block_usage_key": "block-v1:MITx+6.00+2024+type@video+block@abc",
    "block_type": "video",
    "block_display_name": "Lecture 1",
    "rating": 5,
    "comment": "Great",
}


@pytest.mark.django_db
def test_anonymous_cannot_submit():
    resp = APIClient().post(URL, PAYLOAD, format="json")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
def test_authenticated_learner_can_submit():
    user = get_user_model().objects.create(username="learner")
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(URL, PAYLOAD, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert BlockFeedback.objects.filter(user=user, rating=5).count() == 1


@pytest.mark.django_db
def test_non_staff_cannot_list():
    user = get_user_model().objects.create(username="learner")
    client = APIClient()
    client.force_authenticate(user=user)
    assert client.get(URL).status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
def test_staff_can_list_and_filter_by_course():
    staff = get_user_model().objects.create(username="staff", is_staff=True)
    learner = get_user_model().objects.create(username="l2")
    BlockFeedback.objects.create(
        user=learner,
        course_id="course-v1:MITx+6.00+2024",
        block_usage_key="block-v1:MITx+6.00+2024+type@video+block@abc",
        rating=3,
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    resp = client.get(URL, {"course_id": "course-v1:MITx+6.00+2024"})
    assert resp.status_code == status.HTTP_200_OK
    assert resp.data["count"] == 1
