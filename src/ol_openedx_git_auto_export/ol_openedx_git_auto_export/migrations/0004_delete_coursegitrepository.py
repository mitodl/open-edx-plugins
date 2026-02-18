# Generated migration to remove deprecated CourseGitRepository model

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_git_auto_export", "0003_migrate_course_to_content_repo"),
    ]

    operations = [
        migrations.DeleteModel(
            name="CourseGitRepository",
        ),
    ]
