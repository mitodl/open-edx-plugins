# Generated migration to rename course_key field to content_key and change type

import opaque_keys.edx.django.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_git_auto_export", "0002_contentgitrepository"),
    ]

    operations = [
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
