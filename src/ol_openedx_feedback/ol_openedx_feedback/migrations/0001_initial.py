import django.core.validators
import django.db.models.deletion
import opaque_keys.edx.django.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockFeedback",
            fields=[
                (
                    "id",
                    models.AutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "course_id",
                    opaque_keys.edx.django.models.CourseKeyField(
                        db_index=True, max_length=255
                    ),
                ),
                (
                    "course_title",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "block_usage_key",
                    opaque_keys.edx.django.models.UsageKeyField(
                        db_index=True, max_length=255
                    ),
                ),
                ("block_type", models.CharField(blank=True, default="", max_length=64)),
                (
                    "block_display_name",
                    models.CharField(blank=True, default="", max_length=255),
                ),
                (
                    "rating",
                    models.PositiveSmallIntegerField(
                        validators=[
                            django.core.validators.MinValueValidator(1),
                            django.core.validators.MaxValueValidator(5),
                        ]
                    ),
                ),
                ("comment", models.TextField(blank=True, default="")),
                ("created", models.DateTimeField(auto_now_add=True, db_index=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="block_feedback",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created"],
            },
        ),
        migrations.AddIndex(
            model_name="blockfeedback",
            index=models.Index(
                fields=["course_id", "block_usage_key"],
                name="ol_feedback_course_block_idx",
            ),
        ),
    ]
