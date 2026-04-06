from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_calls', '0005_merge_20260406_0735'),
    ]

    operations = [
        migrations.AddField(
            model_name='callsession',
            name='needs_followup',
            field=models.BooleanField(default=False, db_index=True),
        ),
        migrations.AddField(
            model_name='callsession',
            name='staff_notes',
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='conversationturn',
            name='ai_confidence_score',
            field=models.FloatField(null=True, blank=True),
        ),
    ]
