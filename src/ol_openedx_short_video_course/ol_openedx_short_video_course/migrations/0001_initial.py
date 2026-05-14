"""Initial migration for ol_openedx_short_video_course."""

import opaque_keys.edx.django.models
from django.db import migrations, models


class Migration(migrations.Migration):
    """Create initial plugin audit tables."""

    initial = True

    dependencies = []  # type: ignore[var-annotated]

    operations = [
        migrations.CreateModel(
            name="ShortCourseCreationJob",
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
                ("csv_path", models.CharField(max_length=1024)),
                ("run_by_email", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                            ("partial", "Partial"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_summary", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Short Course Creation Job",
                "verbose_name_plural": "Short Course Creation Jobs",
                "app_label": "ol_openedx_short_video_course",
            },
        ),
        migrations.CreateModel(
            name="ShortCourseVariant",
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
                    "batch",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="variants",
                        to="ol_openedx_short_video_course.shortcoursecreationjob",
                    ),
                ),
                (
                    "source_course_key",
                    opaque_keys.edx.django.models.CourseKeyField(max_length=255),
                ),
                (
                    "dest_course_key",
                    opaque_keys.edx.django.models.CourseKeyField(
                        blank=True, max_length=255, null=True
                    ),
                ),
                ("type_code", models.CharField(max_length=50)),
                ("industry_code", models.CharField(max_length=50)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("error_log", models.TextField(blank=True, default="")),
                ("sections_kept", models.IntegerField(default=0)),
                ("sections_removed", models.IntegerField(default=0)),
                ("sections_updated", models.IntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Short Course Variant",
                "verbose_name_plural": "Short Course Variants",
                "app_label": "ol_openedx_short_video_course",
            },
        ),
    ]
