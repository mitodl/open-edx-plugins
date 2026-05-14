"""
Migration 0002: rework ShortCourseVariant for the new course-creation strategy.

Removes:  source_course_key, type_code, industry_code,
          sections_kept, sections_removed, sections_updated, STATUS_RUNNING

Adds:     course_name, sections_created, subsections_created, units_created
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Alter ShortCourseVariant to reflect direct course creation."""

    dependencies = [
        ("ol_openedx_short_video_course", "0001_initial"),
    ]

    operations = [
        # --- Remove obsolete fields ---
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="source_course_key",
        ),
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="type_code",
        ),
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="industry_code",
        ),
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="sections_kept",
        ),
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="sections_removed",
        ),
        migrations.RemoveField(
            model_name="shortcoursevariant",
            name="sections_updated",
        ),
        # --- Add new fields ---
        migrations.AddField(
            model_name="shortcoursevariant",
            name="course_name",
            field=models.CharField(default="", max_length=255),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="shortcoursevariant",
            name="sections_created",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="shortcoursevariant",
            name="subsections_created",
            field=models.IntegerField(default=0),
        ),
        migrations.AddField(
            model_name="shortcoursevariant",
            name="units_created",
            field=models.IntegerField(default=0),
        ),
        # --- Update status choices (drop "running") ---
        migrations.AlterField(
            model_name="shortcoursevariant",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("success", "Success"),
                    ("failed", "Failed"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
