"""
Tests for the migrate_legacy_library_blocks_to_item_bank management command.
"""

import re
from unittest import mock

import pytest
from common.djangoapps.student.tests.factories import UserFactory
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from openedx.core.djangolib.testing.utils import skip_unless_cms

COMMAND_NAME = "migrate_legacy_library_blocks_to_item_bank"
COMMAND_MODULE = (
    "ol_openedx_course_sync.management.commands."
    "migrate_legacy_library_blocks_to_item_bank"
)


def _mock_modulestore(*, existing_course_keys=()):
    """
    Return a mock for the ``modulestore`` callable imported by the command.

    ``has_course`` reports True only for keys in ``existing_course_keys``.
    """
    existing = {str(key) for key in existing_course_keys}
    store = mock.Mock()
    store.has_course.side_effect = lambda key: str(key) in existing
    return mock.Mock(return_value=store)


@skip_unless_cms
@pytest.mark.django_db
class TestMigrateLegacyLibraryBlocksToItemBank:
    """
    Tests for the migrate_legacy_library_blocks_to_item_bank command.
    """

    def test_requires_course_ids_or_all_source_courses(self):
        """
        Command should fail if neither --course-ids nor --all-source-courses
        is provided.
        """
        with pytest.raises(
            CommandError,
            match=re.escape(
                "Either --course-ids or --all-source-courses "
                "argument should be provided."
            ),
        ):
            call_command(COMMAND_NAME)

    def test_mutually_exclusive_course_ids_and_all_source_courses(self):
        """
        Command should fail if both --course-ids and --all-source-courses
        are provided.
        """
        with pytest.raises(
            CommandError,
            match=re.escape(
                "Only one of --course-ids or --all-source-courses "
                "argument should be provided."
            ),
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                "course-v1:edX+DemoX.1+2014",
                "--all-source-courses",
            )

    def test_missing_service_worker_username_setting(self):
        """
        Command should fail if OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME
        is not configured.
        """
        with (
            override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME=None),
            pytest.raises(
                CommandError,
                match=re.escape(
                    "OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME is not set."
                ),
            ),
        ):
            call_command(COMMAND_NAME, "--course-ids", "course-v1:edX+DemoX.1+2014")

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_comma_separated_course_ids_are_queued(self):
        """
        A comma-separated --course-ids value should be split and each course
        key should be queued for migration.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(
                    existing_course_keys=[
                        "course-v1:edX+DemoX.1+2014",
                        "course-v1:edX+DemoX.2+2015",
                    ]
                ),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                "course-v1:edX+DemoX.1+2014,course-v1:edX+DemoX.2+2015",
            )

        not_persisted = False
        mock_migrate_task.delay.assert_has_calls(
            [
                mock.call(user.id, "course-v1:edX+DemoX.1+2014", not_persisted),
                mock.call(user.id, "course-v1:edX+DemoX.2+2015", not_persisted),
            ]
        )
        expected_call_count = 2
        assert mock_migrate_task.delay.call_count == expected_call_count

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_course_ids_with_surrounding_whitespace_are_stripped(self):
        """
        Whitespace around comma-separated course keys should be stripped.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(
                    existing_course_keys=[
                        "course-v1:edX+DemoX.1+2014",
                        "course-v1:edX+DemoX.2+2015",
                    ]
                ),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                " course-v1:edX+DemoX.1+2014 , course-v1:edX+DemoX.2+2015 ",
            )

        not_persisted = False
        mock_migrate_task.delay.assert_has_calls(
            [
                mock.call(user.id, "course-v1:edX+DemoX.1+2014", not_persisted),
                mock.call(user.id, "course-v1:edX+DemoX.2+2015", not_persisted),
            ]
        )

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_invalid_course_key_is_skipped(self):
        """
        An invalid course key in --course-ids should be skipped, and valid
        course keys should still be queued.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(existing_course_keys=["course-v1:edX+DemoX.1+2014"]),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                "not-a-valid-course-key,course-v1:edX+DemoX.1+2014",
            )

        not_persisted = False
        mock_migrate_task.delay.assert_called_once_with(
            user.id, "course-v1:edX+DemoX.1+2014", not_persisted
        )

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_course_not_in_modulestore_is_skipped(self):
        """
        A course key that parses but does not exist in the modulestore
        should be skipped, and remaining valid course keys should still be
        queued.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(existing_course_keys=["course-v1:edX+DemoX.2+2015"]),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                "course-v1:edX+DemoX.1+2014,course-v1:edX+DemoX.2+2015",
            )

        not_persisted = False
        mock_migrate_task.delay.assert_called_once_with(
            user.id, "course-v1:edX+DemoX.2+2015", not_persisted
        )

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_all_source_courses_uses_get_all_source_courses(self):
        """
        --all-source-courses should queue migration for every course
        returned by get_all_source_courses.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.get_all_source_courses",
                return_value=["course-v1:edX+DemoX.1+2014"],
            ),
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(existing_course_keys=["course-v1:edX+DemoX.1+2014"]),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(COMMAND_NAME, "--all-source-courses")

        not_persisted = False
        mock_migrate_task.delay.assert_called_once_with(
            user.id, "course-v1:edX+DemoX.1+2014", not_persisted
        )

    @override_settings(OL_OPENEDX_COURSE_SYNC_SERVICE_WORKER_USERNAME="service_worker")
    def test_persist_publish_state_flag_is_forwarded(self):
        """
        --persist-publish-state should be forwarded to the migration task.
        """
        user = UserFactory.create(username="service_worker")
        with (
            mock.patch(
                f"{COMMAND_MODULE}.modulestore",
                _mock_modulestore(existing_course_keys=["course-v1:edX+DemoX.1+2014"]),
            ),
            mock.patch(
                f"{COMMAND_MODULE}.migrate_course_legacy_library_blocks_to_item_bank"
            ) as mock_migrate_task,
        ):
            call_command(
                COMMAND_NAME,
                "--course-ids",
                "course-v1:edX+DemoX.1+2014",
                "--persist-publish-state",
            )

        persisted = True
        mock_migrate_task.delay.assert_called_once_with(
            user.id, "course-v1:edX+DemoX.1+2014", persisted
        )
