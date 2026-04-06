"""
Add CallSession and ConversationTurn for multi-turn conversation support.
Depends on 0002_callrecord_response_audio_path.
"""
import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('voice_calls', '0002_callrecord_response_audio_path'),
    ]

    operations = [
        # ── CallSession ───────────────────────────────────────────────────────
        migrations.CreateModel(
            name='CallSession',
            fields=[
                ('id',         models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('caller_number',      models.CharField(db_index=True, max_length=64)),
                ('started_at',         models.DateTimeField(auto_now_add=True)),
                ('ended_at',           models.DateTimeField(blank=True, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('active',      'Active'),
                        ('completed',   'Completed'),
                        ('transferred', 'Transferred to Human'),
                        ('failed',      'Failed'),
                    ],
                    db_index=True, default='active', max_length=16,
                )),
                ('transfer_triggered', models.BooleanField(default=False)),
                ('transfer_reason',    models.TextField(blank=True, null=True)),
                ('failure_reason',     models.TextField(blank=True, null=True)),
                ('total_turns',        models.PositiveIntegerField(default=0)),
            ],
            options={
                'verbose_name': 'Call Session',
                'verbose_name_plural': 'Call Sessions',
                'db_table': 'call_sessions',
                'ordering': ['-started_at'],
            },
        ),
        migrations.AddIndex(
            model_name='callsession',
            index=models.Index(fields=['status', 'started_at'], name='idx_session_status_started'),
        ),
        migrations.AddIndex(
            model_name='callsession',
            index=models.Index(fields=['caller_number'], name='idx_session_caller'),
        ),

        # ── ConversationTurn ──────────────────────────────────────────────────
        migrations.CreateModel(
            name='ConversationTurn',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('session', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='turns',
                    to='voice_calls.callsession',
                    db_index=True,
                )),
                ('turn_number',              models.PositiveIntegerField()),
                ('audio_input_path',         models.CharField(max_length=512)),
                ('audio_input_exists',       models.BooleanField(blank=True, null=True)),
                ('audio_input_size',         models.PositiveBigIntegerField(blank=True, null=True)),
                ('transcript_text',          models.TextField(blank=True, null=True)),
                ('transcription_started_at', models.DateTimeField(blank=True, null=True)),
                ('transcription_completed_at', models.DateTimeField(blank=True, null=True)),
                ('ai_response_text',         models.TextField(blank=True, null=True)),
                ('llm_started_at',           models.DateTimeField(blank=True, null=True)),
                ('llm_completed_at',         models.DateTimeField(blank=True, null=True)),
                ('audio_response_path',      models.CharField(blank=True, max_length=512, null=True)),
                ('audio_response_exists',    models.BooleanField(blank=True, null=True)),
                ('audio_response_size',      models.PositiveBigIntegerField(blank=True, null=True)),
                ('tts_started_at',           models.DateTimeField(blank=True, null=True)),
                ('tts_completed_at',         models.DateTimeField(blank=True, null=True)),
                ('transfer_needed',          models.BooleanField(default=False)),
                ('transfer_reason',          models.CharField(blank=True, max_length=256, null=True)),
                ('status', models.CharField(
                    choices=[
                        ('pending',    'Pending'),
                        ('processing', 'Processing'),
                        ('ready',      'Ready'),
                        ('failed',     'Failed'),
                    ],
                    db_index=True, default='pending', max_length=16,
                )),
                ('error_message', models.TextField(blank=True, null=True)),
                ('created_at',    models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Conversation Turn',
                'verbose_name_plural': 'Conversation Turns',
                'db_table': 'conversation_turns',
                'ordering': ['session', 'turn_number'],
            },
        ),
        migrations.AddConstraint(
            model_name='conversationturn',
            constraint=models.UniqueConstraint(
                fields=['session', 'turn_number'],
                name='uq_turn_session_number',
            ),
        ),
        migrations.AddIndex(
            model_name='conversationturn',
            index=models.Index(fields=['session', 'status'], name='idx_turn_session_status'),
        ),
    ]
