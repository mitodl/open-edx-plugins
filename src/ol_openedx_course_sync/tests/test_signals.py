from unittest import mock

import pytest
from common.djangoapps.course_action_state.models import CourseRerunState
from django.core.exceptions import ValidationError
from ol_openedx_course_sync.constants import COURSE_RERUN_STATE_SUCCEEDED
from ol_openedx_course_sync.models import CourseSyncMap, CourseSyncParentOrg
from openedx.core.djangolib.testing.utils import skip_unless_cms


@skip_unless_cms
@pytest.mark.django_db()
@pytest.mark.parametrize(
    ("state", "create_org", "sync_map_exists"),
    [
        ("PENDING", True, False),
        (COURSE_RERUN_STATE_SUCCEEDED, False, False),
        (COURSE_RERUN_STATE_SUCCEEDED, True, True),
    ],
)
def test_signal_does_nothing_in_invalid_conditions(state, create_org, sync_map_exists):
    """
    Test that signal creates CourseSyncMap only when:
    - CourseRerunState is in COURSE_RERUN_STATE_SUCCEEDED state
    - CourseSyncParentOrg exists for the organization
    """
    if create_org:
        CourseSyncParentOrg.objects.create(organization="TestOrg")

    course_rerun_state = CourseRerunState.objects.create(
        state=state,
        course_key="course-v1:TestOrg+NewCourse+2025",
        source_course_key="course-v1:TestOrg+OldCourse+2024",
    )
    assert CourseSyncMap.objects.exists() == sync_map_exists

    if sync_map_exists:
        sync_map = CourseSyncMap.objects.get(
            source_course=course_rerun_state.source_course_key,
        )
        assert str(course_rerun_state.course_key) in str(sync_map.target_courses)


@skip_unless_cms
@pytest.mark.django_db()
@mock.patch("ol_openedx_course_sync.signals.log")
def test_signal_logs_validation_error_on_create(mock_log):
    """
    Test that signal logs an error when CourseSyncMap creation fails.
    """
    CourseSyncParentOrg.objects.create(organization="TestOrg")

    with mock.patch(
        "ol_openedx_course_sync.models.CourseSyncMap.objects.get_or_create"
    ) as mock_get_or_create:
        mock_get_or_create.side_effect = ValidationError("Mock error")

        instance = CourseRerunState.objects.create(
            state=COURSE_RERUN_STATE_SUCCEEDED,
            course_key="course-v1:TestOrg+NewCourse+2025",
            source_course_key="course-v1:TestOrg+OldCourse+2024",
        )

        mock_log.exception.assert_called_once_with(
            "Failed to create CourseSyncMap for %s",
            instance.source_course_key,
        )


@skip_unless_cms
@pytest.mark.django_db()
@mock.patch("ol_openedx_course_sync.signals.log")
def test_signal_logs_validation_error_on_save(mock_log):
    """
    Test that signal logs an error when CourseSyncMap save fails.
    """
    CourseSyncParentOrg.objects.create(organization="TestOrg")

    instance = CourseRerunState.objects.create(
        state=COURSE_RERUN_STATE_SUCCEEDED,
        course_key="course-v1:TestOrg+NewCourse+2025",
        source_course_key="course-v1:TestOrg+OldCourse+2024",
    )

    with mock.patch("ol_openedx_course_sync.models.CourseSyncMap.save") as mock_save:
        mock_save.side_effect = ValidationError("save error")

        # Manually trigger the signal
        from ol_openedx_course_sync.signals import (
            listen_for_course_rerun_state_post_save,
        )

        listen_for_course_rerun_state_post_save(
            sender=CourseRerunState, instance=instance
        )

        mock_log.exception.assert_called_once_with(
            "Failed to update CourseSyncMap for %s",
            instance.source_course_key,
        )
