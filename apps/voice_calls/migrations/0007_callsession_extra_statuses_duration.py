from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_calls', '0006_callsession_portal_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='callsession',
            name='duration_seconds',
            field=models.IntegerField(null=True, blank=True),
        ),
        migrations.AlterField(
            model_name='callsession',
            name='status',
            field=models.CharField(
                max_length=16,
                choices=[
                    ('active',          'Active'),
                    ('completed',       'Completed'),
                    ('transferred',     'Transferred to Human'),
                    ('failed',          'Failed'),
                    ('ended_by_caller', 'Ended by Caller'),
                    ('abandoned',       'Abandoned'),
                ],
                default='active',
                db_index=True,
            ),
        ),
        migrations.AddField(
            model_name='conversationturn',
            name='closing_detected',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='conversationturn',
            name='rag_failure',
            field=models.BooleanField(default=False),
        ),
    ]
