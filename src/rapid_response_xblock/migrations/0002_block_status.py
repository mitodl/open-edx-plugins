from django.db import migrations, models
import opaque_keys.edx.django.models


class Migration(migrations.Migration):

    dependencies = [
        ('rapid_response_xblock', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='RapidResponseBlockStatus',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('usage_key', opaque_keys.edx.django.models.UsageKeyField(max_length=255, db_index=True)),
                ('open', models.BooleanField(default=False)),
                ('course_key', opaque_keys.edx.django.models.CourseKeyField(max_length=255, db_index=True)),
            ],
        ),
    ]
