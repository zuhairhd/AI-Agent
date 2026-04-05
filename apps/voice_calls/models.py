import uuid
from django.db import models
from apps.core.models import TimeStampedModel


class CallRecord(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING     = 'pending',     'Pending'
        PROCESSING  = 'processing',  'Processing'
        ANSWERED    = 'answered',    'Answered'
        AUDIO_READY = 'audio_ready', 'Audio Ready'
        FAILED      = 'failed',      'Failed'

    caller_number      = models.CharField(max_length=64, db_index=True)
    audio_file_path    = models.CharField(max_length=512)
    transcript_text    = models.TextField(blank=True, null=True)
    gpt_response_text  = models.TextField(blank=True, null=True)
    # Path to the TTS-generated WAV file Asterisk will play back
    response_audio_path = models.CharField(max_length=512, blank=True, null=True)
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'call_records'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_call_status_created'),
        ]
        verbose_name = 'Call Record'
        verbose_name_plural = 'Call Records'

    def __str__(self):
        return f"Call from {self.caller_number} [{self.status}] at {self.created_at:%Y-%m-%d %H:%M}"


class CallEvent(models.Model):
    class EventType(models.TextChoices):
        STARTED     = 'started',     'Started'
        TRANSCRIBED = 'transcribed', 'Transcribed'
        ANSWERED    = 'answered',    'Answered'
        TTS_DONE    = 'tts_done',    'TTS Done'
        FAILED      = 'failed',      'Failed'
        RETRY       = 'retry',       'Retry'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call = models.ForeignKey(
        CallRecord,
        on_delete=models.CASCADE,
        related_name='events',
        db_index=True,
    )
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    payload    = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'call_events'
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['call', 'event_type'], name='idx_event_call_type'),
        ]
        verbose_name = 'Call Event'
        verbose_name_plural = 'Call Events'

    def __str__(self):
        return f"[{self.event_type}] on call {self.call_id} at {self.created_at:%H:%M:%S}"
