"""
Tests for ol-openedx-course-sync signal handlers
"""

from unittest import mock

import pytest
from common.djangoapps.course_action_state.models import CourseRerunState
from django.core.exceptions import ValidationError
from ol_openedx_course_sync.constants import COURSE_RERUN_STATE_SUCCEEDED
from ol_openedx_course_sync.models import CourseSyncMapping, CourseSyncOrganization
from ol_openedx_course_sync.signals import listen_for_course_publish
from opaque_keys.edx.locator import CourseLocator
from openedx.core.djangolib.testing.utils import skip_unless_cms
from xmodule.modulestore.django import SignalHandler
from xmodule.modulestore.tests.django_utils import SharedModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory


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
    Test that signal creates CourseSyncMapping only when:
    - CourseRerunState is in COURSE_RERUN_STATE_SUCCEEDED state
    - CourseSyncOrganization exists for the organization
    """
    if create_org:
        CourseSyncOrganization.objects.create(organization="TestOrg")

    course_rerun_state = CourseRerunState.objects.create(
        state=state,
        course_key="course-v1:TestOrg+NewCourse+2025",
        source_course_key="course-v1:TestOrg+OldCourse+2024",
    )
    assert CourseSyncMapping.objects.exists() == sync_map_exists

    if sync_map_exists:
        sync_map = CourseSyncMapping.objects.get(
            source_course=course_rerun_state.source_course_key,
        )
        assert str(course_rerun_state.course_key) == str(sync_map.target_course)


@skip_unless_cms
@pytest.mark.django_db()
@mock.patch("ol_openedx_course_sync.signals.log")
def test_signal_logs_validation_error_on_create(mock_log):
    """
    Test that signal logs an error when CourseSyncMapping creation fails.
    """
    CourseSyncOrganization.objects.create(organization="TestOrg")

    with mock.patch(
        "ol_openedx_course_sync.models.CourseSyncMapping.objects.create"
    ) as mock_get_or_create:
        mock_get_or_create.side_effect = ValidationError("Mock error")

        instance = CourseRerunState.objects.create(
            state=COURSE_RERUN_STATE_SUCCEEDED,
            course_key="course-v1:TestOrg+NewCourse+2025",
            source_course_key="course-v1:TestOrg+OldCourse+2024",
        )

        mock_log.exception.assert_called_once_with(
            "Failed to create CourseSyncMapping for %s",
            instance.source_course_key,
        )


@skip_unless_cms
class TestCoursePublishSignal(SharedModuleStoreTestCase):
    """
    Test the course publish signal handler.
    """

    ENABLED_SIGNALS = ["course_published"]

    def setUp(self):
        super().setUp()
        SignalHandler.course_published.disconnect(listen_for_course_publish)
        self.source_course_key = CourseLocator.from_string(
            "course-v1:TestOrg+CS101+2025"
        )
        CourseFactory.create(
            org="TestOrg",
            number="CS101",
            run="2025",
            display_name="Test Course",
        )

    def tearDown(self):
        super().tearDown()
        SignalHandler.course_published.disconnect(listen_for_course_publish)

    @mock.patch("ol_openedx_course_sync.signals.async_course_sync")
    def test_publish_signal_triggers_copy_tasks(self, mock_task):
        """
        Test that the course publish signal triggers the async_course_sync task
        """
        CourseSyncOrganization.objects.create(organization="TestOrg")
        CourseSyncMapping.objects.create(
            source_course=str(self.source_course_key),
            target_course="course-v1:TestOrg+Target1+2025",
        )
        CourseSyncMapping.objects.create(
            source_course=str(self.source_course_key),
            target_course="course-v1:TestOrg+Target2+2025",
        )
        SignalHandler.course_published.connect(listen_for_course_publish)
        SignalHandler.course_published.send(
            sender=None, course_key=self.source_course_key
        )
        calls = [
            mock.call.delay(
                str(self.source_course_key), "course-v1:TestOrg+Target1+2025"
            ),
            mock.call.delay(
                str(self.source_course_key), "course-v1:TestOrg+Target2+2025"
            ),
        ]
        mock_task.assert_has_calls(calls, any_order=True)
