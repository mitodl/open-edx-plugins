# Generated migration for ContentGitRepository model

import django.utils.timezone
import model_utils.fields
import opaque_keys.edx.django.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_git_auto_export", "0001_initial"),
    ]  # type: ignore  # noqa: PGH003

    operations = [
        migrations.CreateModel(
            name="ContentGitRepository",
            fields=[
                (
                    "created",
                    model_utils.fields.AutoCreatedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="created",
                    ),
                ),
                (
                    "modified",
                    model_utils.fields.AutoLastModifiedField(
                        default=django.utils.timezone.now,
                        editable=False,
                        verbose_name="modified",
                    ),
                ),
                (
                    "content_key",
                    opaque_keys.edx.django.models.LearningContextKeyField(
                        max_length=255, primary_key=True, serialize=False
                    ),
                ),
                ("git_url", models.CharField(max_length=255)),
                ("is_export_enabled", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Content Git Repository",
                "verbose_name_plural": "Content Git Repositories",
                "ordering": ["-created"],
            },
        ),
    ]
