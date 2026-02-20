# Generated migration for renaming CourseGitRepository to ContentGitRepository

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_git_auto_export", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="CourseGitRepository",
            new_name="ContentGitRepository",
        ),
    ]
