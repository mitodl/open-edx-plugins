"""
Tests for the course sync admin
"""

import pytest
from common.djangoapps.student.tests.factories import UserFactory
from django.conf import settings
from django.contrib import admin
from django.test import RequestFactory
from ol_openedx_course_sync.models import CourseSyncMapping

SYNC_ACTIONS = {"sync_course_content", "sync_course_assets"}


@pytest.mark.django_db
def test_sync_actions_only_in_cms_admin():
    """
    The mapping admin is registered in both LMS and CMS, but only the CMS
    admin offers the sync actions.
    """
    request = RequestFactory().get("/admin/")
    request.user = UserFactory(is_staff=True, is_superuser=True)
    model_admin = admin.site._registry[CourseSyncMapping]  # noqa: SLF001

    offered = SYNC_ACTIONS & set(model_admin.get_actions(request))

    assert offered == (SYNC_ACTIONS if settings.SERVICE_VARIANT == "cms" else set())
