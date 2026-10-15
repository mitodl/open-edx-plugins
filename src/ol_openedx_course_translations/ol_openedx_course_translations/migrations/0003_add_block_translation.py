import opaque_keys.edx.django.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ol_openedx_course_translations", "0002_add_translation_benchmark_models"),
    ]

    operations = [
        migrations.CreateModel(
            name="BlockTranslation",
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
                    "course_key",
                    opaque_keys.edx.django.models.CourseKeyField(
                        db_index=True, max_length=255
                    ),
                ),
                (
                    "usage_key",
                    opaque_keys.edx.django.models.UsageKeyField(max_length=255),
                ),
                ("field", models.CharField(max_length=64)),
                (
                    "language",
                    models.CharField(
                        help_text=(
                            "Django language code, lowercase (e.g. 'fr', 'es-419')"
                        ),
                        max_length=16,
                    ),
                ),
                (
                    "source_hash",
                    models.CharField(
                        help_text=(
                            "sha256 of the source value this row was translated from"
                        ),
                        max_length=64,
                    ),
                ),
                ("translated_value", models.TextField()),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("auto", "Auto"),
                            ("reviewed", "Reviewed"),
                            ("stale", "Stale"),
                        ],
                        default="auto",
                        max_length=16,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("usage_key", "field", "language"),
                        name="unique_translation_per_block_field_language",
                    )
                ],
            },
        ),
    ]
