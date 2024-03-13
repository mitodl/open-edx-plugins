from django.db import migrations, models
import jsonfield.fields
from django.conf import settings
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import opaque_keys.edx.django.models


# pylint: skip-file

class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='RapidResponseSubmission',
            fields=[
                ('id', models.AutoField(
                    verbose_name='ID',
                    serialize=False,
                    auto_created=True,
                    primary_key=True,
                )),
                ('created', model_utils.fields.AutoCreatedField(
                    default=django.utils.timezone.now,
                    verbose_name='created',
                    editable=False,
                )),
                ('modified', model_utils.fields.AutoLastModifiedField(
                    default=django.utils.timezone.now,
                    verbose_name='modified',
                    editable=False,
                )),
                ('problem_id', opaque_keys.edx.django.models.UsageKeyField(
                    max_length=255,
                    db_index=True,
                )),
                ('course_id', opaque_keys.edx.django.models.CourseKeyField(
                    max_length=255,
                    db_index=True,
                )),
                ('answer_id', models.CharField(
                    max_length=255,
                    null=True,
                )),
                ('answer_text', models.CharField(
                    max_length=4096,
                    null=True,
                )),
                ('event', jsonfield.fields.JSONField()),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.SET_NULL,
                    to=settings.AUTH_USER_MODEL,
                    null=True,
                )),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
