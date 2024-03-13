from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('rapid_response_xblock', '0002_block_status'),
    ]

    operations = [
        migrations.RenameField(
            model_name='rapidresponseblockstatus',
            old_name='usage_key',
            new_name='problem_usage_key',
        ),
        migrations.RenameField(
            model_name='rapidresponsesubmission',
            old_name='course_id',
            new_name='course_key',
        ),
        migrations.RenameField(
            model_name='rapidresponsesubmission',
            old_name='problem_id',
            new_name='problem_usage_key',
        ),
    ]
