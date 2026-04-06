"""
Add language field to CallSession for bilingual support.
Depends on 0003_callsession_conversationturn.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_calls', '0003_callsession_conversationturn'),
    ]

    operations = [
        migrations.AddField(
            model_name='callsession',
            name='language',
            field=models.CharField(
                max_length=8,
                default='en',
                db_index=True,
                help_text="Language selected by caller: 'en' or 'ar'.",
            ),
        ),
    ]
