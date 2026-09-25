"""
Rename existing S3 export task statuses so Studio doesn't treat them as its own
course exports.

S3 export tasks used to share Studio's "Export of <course key>" status name. Studio
looks up a course's latest export status by that name and expects an "Output"
artifact, which S3 export tasks don't create, so its export status page failed
whenever an S3 export was the latest one for a course.
"""

from django.db import migrations
from django.db.models import Value
from django.db.models.functions import Concat, Substr

S3_EXPORT_TASK_CLASS = "ol_openedx_course_export.tasks.task_upload_course_s3"
OLD_NAME_PREFIX = "Export of "
NEW_NAME_PREFIX = "S3 export of "


def _replace_name_prefix(apps, old_prefix, new_prefix):
    UserTaskStatus = apps.get_model("user_tasks", "UserTaskStatus")
    UserTaskStatus.objects.filter(
        task_class=S3_EXPORT_TASK_CLASS, name__startswith=old_prefix
    ).update(name=Concat(Value(new_prefix), Substr("name", len(old_prefix) + 1)))


def rename_s3_export_task_statuses(apps, schema_editor):  # noqa: ARG001
    """Give S3 export task statuses their own name."""
    _replace_name_prefix(apps, OLD_NAME_PREFIX, NEW_NAME_PREFIX)


def restore_s3_export_task_status_names(apps, schema_editor):  # noqa: ARG001
    """Restore the Studio export name on S3 export task statuses."""
    _replace_name_prefix(apps, NEW_NAME_PREFIX, OLD_NAME_PREFIX)


class Migration(migrations.Migration):
    dependencies = [
        ("user_tasks", "0005_mariadb_uuid_conversion"),
    ]

    operations = [
        migrations.RunPython(
            rename_s3_export_task_statuses, restore_s3_export_task_status_names
        ),
    ]
