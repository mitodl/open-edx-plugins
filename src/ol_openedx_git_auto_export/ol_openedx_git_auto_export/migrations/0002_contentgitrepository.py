# Generated migration for renaming CourseGitRepository to ContentGitRepository

import opaque_keys.edx.django.models
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
        migrations.RenameField(
            model_name="contentgitrepository",
            old_name="course_key",
            new_name="content_key",
        ),
        migrations.AlterField(
            model_name="contentgitrepository",
            name="content_key",
            field=opaque_keys.edx.django.models.LearningContextKeyField(
                max_length=255, primary_key=True, serialize=False
            ),
        ),
    ]
