"""
Tests for the migration that renames existing S3 export task statuses.
"""

from importlib import import_module
from uuid import uuid4

from common.djangoapps.student.tests.factories import UserFactory
from django.apps import apps
from django.test import TestCase
from user_tasks.models import UserTaskStatus

migration = import_module(
    "ol_openedx_course_export.migrations.0001_rename_s3_export_task_statuses"
)

COURSE_KEY = "course-v1:MITx+Test+2026"


class RenameS3ExportTaskStatusesTest(TestCase):
    """
    Tests for renaming S3 export task statuses away from Studio's export name.
    """

    def setUp(self):
        super().setUp()
        user = UserFactory()
        self.s3_export = self._create_status(
            user, migration.S3_EXPORT_TASK_CLASS, f"Export of {COURSE_KEY}"
        )
        self.studio_export = self._create_status(
            user,
            "cms.djangoapps.contentstore.tasks.export_olx",
            f"Export of {COURSE_KEY}",
        )

    @staticmethod
    def _create_status(user, task_class, name):
        return UserTaskStatus.objects.create(
            user=user,
            task_id=str(uuid4()),
            task_class=task_class,
            name=name,
            total_steps=2,
            state=UserTaskStatus.SUCCEEDED,
        )

    def test_renames_only_s3_export_statuses(self):
        migration.rename_s3_export_task_statuses(apps, None)

        self.s3_export.refresh_from_db()
        self.studio_export.refresh_from_db()
        assert self.s3_export.name == f"S3 export of {COURSE_KEY}"
        assert self.studio_export.name == f"Export of {COURSE_KEY}"

    def test_reverse_restores_the_old_name(self):
        migration.rename_s3_export_task_statuses(apps, None)
        migration.restore_s3_export_task_status_names(apps, None)

        self.s3_export.refresh_from_db()
        self.studio_export.refresh_from_db()
        assert self.s3_export.name == f"Export of {COURSE_KEY}"
        assert self.studio_export.name == f"Export of {COURSE_KEY}"
