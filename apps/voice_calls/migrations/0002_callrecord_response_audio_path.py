"""
Add response_audio_path to CallRecord and TTS_DONE event type to CallEvent.
Also adds 'audio_ready' to CallRecord.status choices.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_calls', '0001_initial'),
    ]

    operations = [
        # New field: path to the TTS WAV file Asterisk plays back
        migrations.AddField(
            model_name='callrecord',
            name='response_audio_path',
            field=models.CharField(blank=True, max_length=512, null=True),
        ),
        # Extend status choices to include 'audio_ready'
        migrations.AlterField(
            model_name='callrecord',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',     'Pending'),
                    ('processing',  'Processing'),
                    ('answered',    'Answered'),
                    ('audio_ready', 'Audio Ready'),
                    ('failed',      'Failed'),
                ],
                db_index=True,
                default='pending',
                max_length=16,
            ),
        ),
        # Extend event_type choices to include 'tts_done'
        migrations.AlterField(
            model_name='callevent',
            name='event_type',
            field=models.CharField(
                choices=[
                    ('started',     'Started'),
                    ('transcribed', 'Transcribed'),
                    ('answered',    'Answered'),
                    ('tts_done',    'TTS Done'),
                    ('failed',      'Failed'),
                    ('retry',       'Retry'),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
    ]
