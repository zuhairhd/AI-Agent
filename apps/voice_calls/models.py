import uuid
from django.db import models
from apps.core.models import TimeStampedModel


class CallRecord(TimeStampedModel):
    """Legacy single-turn call record — preserved for backward compatibility."""
    class Status(models.TextChoices):
        PENDING     = 'pending',     'Pending'
        PROCESSING  = 'processing',  'Processing'
        ANSWERED    = 'answered',    'Answered'
        AUDIO_READY = 'audio_ready', 'Audio Ready'
        FAILED      = 'failed',      'Failed'

    caller_number       = models.CharField(max_length=64, db_index=True)
    audio_file_path     = models.CharField(max_length=512)
    transcript_text     = models.TextField(blank=True, null=True)
    gpt_response_text   = models.TextField(blank=True, null=True)
    response_audio_path = models.CharField(max_length=512, blank=True, null=True)
    status = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    answered_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'call_records'
        ordering = ['-created_at']
        indexes = [models.Index(fields=['status', 'created_at'], name='idx_call_status_created')]
        verbose_name = 'Call Record (Legacy)'
        verbose_name_plural = 'Call Records (Legacy)'

    def __str__(self):
        return f"Call from {self.caller_number} [{self.status}] at {self.created_at:%Y-%m-%d %H:%M}"


class CallEvent(models.Model):
    """Event log entry for a legacy CallRecord."""
    class EventType(models.TextChoices):
        STARTED     = 'started',     'Started'
        TRANSCRIBED = 'transcribed', 'Transcribed'
        ANSWERED    = 'answered',    'Answered'
        TTS_DONE    = 'tts_done',    'TTS Done'
        FAILED      = 'failed',      'Failed'
        RETRY       = 'retry',       'Retry'

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    call       = models.ForeignKey(CallRecord, on_delete=models.CASCADE, related_name='events', db_index=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    payload    = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'call_events'
        ordering = ['created_at']
        indexes = [models.Index(fields=['call', 'event_type'], name='idx_event_call_type')]
        verbose_name = 'Call Event (Legacy)'
        verbose_name_plural = 'Call Events (Legacy)'

    def __str__(self):
        return f"[{self.event_type}] on call {self.call_id} at {self.created_at:%H:%M:%S}"


# ---------------------------------------------------------------------------
# Production multi-turn session models
# ---------------------------------------------------------------------------

class CallSession(TimeStampedModel):
    """
    One session = one inbound PSTN call.
    Created at call start, holds N ConversationTurns, closed when call ends.
    Managed via POST /api/session/start/ and POST /api/session/<id>/end/.
    """
    class Status(models.TextChoices):
        ACTIVE      = 'active',      'Active'
        COMPLETED   = 'completed',   'Completed'
        TRANSFERRED = 'transferred', 'Transferred to Human'
        FAILED      = 'failed',      'Failed'

    # Explicit UUID primary key — consistent with ConversationTurn and the migration.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    caller_number      = models.CharField(max_length=64, db_index=True)
    started_at         = models.DateTimeField(auto_now_add=True)
    ended_at           = models.DateTimeField(null=True, blank=True)
    status             = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.ACTIVE, db_index=True,
    )
    # Portal fields
    needs_followup = models.BooleanField(default=False, db_index=True)
    staff_notes    = models.TextField(blank=True, null=True)

    # Becomes True the moment any turn triggers a transfer decision
    transfer_triggered = models.BooleanField(default=False)
    # Rule name or 'llm_flag' that caused the transfer
    transfer_reason    = models.TextField(blank=True, null=True)
    # Populated when status == 'failed'
    failure_reason     = models.TextField(blank=True, null=True)
    # Incremented by each successfully completed turn
    total_turns        = models.PositiveIntegerField(default=0)
    # Language selected by the caller in the bilingual menu ('en' or 'ar')
    language           = models.CharField(max_length=8, default='en', db_index=True)

    class Meta:
        db_table = 'call_sessions'
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status', 'started_at'], name='idx_session_status_started'),
            models.Index(fields=['caller_number'],         name='idx_session_caller'),
        ]
        verbose_name = 'Call Session'
        verbose_name_plural = 'Call Sessions'

    def __str__(self):
        return f"Session {self.caller_number} [{self.status}] {self.started_at:%Y-%m-%d %H:%M}"


class ConversationTurn(models.Model):
    """
    One turn = caller speaks → STT → LLM → TTS → Asterisk plays response.

    Every processing stage is time-stamped. Input and output audio files are
    checked for existence and size when the Celery task runs, providing an
    audit trail independent of what the filesystem looks like later.
    """
    class Status(models.TextChoices):
        PENDING    = 'pending',    'Pending'
        PROCESSING = 'processing', 'Processing'
        READY      = 'ready',      'Ready'
        FAILED     = 'failed',     'Failed'

    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session     = models.ForeignKey(CallSession, on_delete=models.CASCADE, related_name='turns', db_index=True)
    turn_number = models.PositiveIntegerField()

    # ── Input audio (recorded by Asterisk) ───────────────────────────────────
    audio_input_path   = models.CharField(max_length=512)
    audio_input_exists = models.BooleanField(null=True, blank=True)   # snapshot at task start
    audio_input_size   = models.PositiveBigIntegerField(null=True, blank=True)

    # ── Speech-to-text ────────────────────────────────────────────────────────
    transcript_text            = models.TextField(blank=True, null=True)
    transcription_started_at   = models.DateTimeField(null=True, blank=True)
    transcription_completed_at = models.DateTimeField(null=True, blank=True)

    # ── LLM response ──────────────────────────────────────────────────────────
    ai_response_text = models.TextField(blank=True, null=True)
    llm_started_at   = models.DateTimeField(null=True, blank=True)
    llm_completed_at = models.DateTimeField(null=True, blank=True)
    # AI confidence score for this turn (0.0–1.0); set by LLM service
    ai_confidence_score = models.FloatField(null=True, blank=True)

    # ── TTS output audio (played back by Asterisk) ────────────────────────────
    audio_response_path   = models.CharField(max_length=512, blank=True, null=True)
    audio_response_exists = models.BooleanField(null=True, blank=True)
    audio_response_size   = models.PositiveBigIntegerField(null=True, blank=True)
    tts_started_at        = models.DateTimeField(null=True, blank=True)
    tts_completed_at      = models.DateTimeField(null=True, blank=True)

    # ── Transfer decision ─────────────────────────────────────────────────────
    transfer_needed = models.BooleanField(default=False)
    # E.g. 'explicit_request:human', 'frustration:angry', 'llm_flag', 'repeated_failures'
    transfer_reason = models.CharField(max_length=256, blank=True, null=True)

    # ── Status & errors ───────────────────────────────────────────────────────
    status        = models.CharField(
        max_length=16, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    error_message = models.TextField(blank=True, null=True)
    created_at    = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'conversation_turns'
        ordering = ['session', 'turn_number']
        indexes = [
            models.Index(fields=['session', 'status'], name='idx_turn_session_status'),
        ]
        verbose_name = 'Conversation Turn'
        verbose_name_plural = 'Conversation Turns'

    def __str__(self):
        return f"Turn {self.turn_number} | session={self.session_id} [{self.status}]"
