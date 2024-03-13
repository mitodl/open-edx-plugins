from django.db import migrations, models
import django.db.models.deletion
import django.utils.timezone
import model_utils.fields
import opaque_keys.edx.django.models


class Migration(migrations.Migration):

    dependencies = [
        ('rapid_response_xblock', '0003_rename_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='RapidResponseRun',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created', model_utils.fields.AutoCreatedField(default=django.utils.timezone.now, verbose_name='created', editable=False)),
                ('modified', model_utils.fields.AutoLastModifiedField(default=django.utils.timezone.now, verbose_name='modified', editable=False)),
                ('name', models.TextField()),
                ('problem_usage_key', opaque_keys.edx.django.models.UsageKeyField(max_length=255, db_index=True)),
                ('course_key', opaque_keys.edx.django.models.CourseKeyField(max_length=255, db_index=True)),
                ('open', models.BooleanField(default=False)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.DeleteModel(
            name='RapidResponseBlockStatus',
        ),
        migrations.RemoveField(
            model_name='rapidresponsesubmission',
            name='course_key',
        ),
        migrations.RemoveField(
            model_name='rapidresponsesubmission',
            name='problem_usage_key',
        ),
        migrations.AddField(
            model_name='rapidresponsesubmission',
            name='run',
            field=models.ForeignKey(on_delete=django.db.models.deletion.SET_NULL, to='rapid_response_xblock.RapidResponseRun', null=True),
        ),
    ]
