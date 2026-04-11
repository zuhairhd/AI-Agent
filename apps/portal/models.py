import uuid
from django.db import models
from django.contrib.auth import get_user_model
from apps.core.models import TimeStampedModel

User = get_user_model()


class Alert(TimeStampedModel):
    """Auto-generated alert when a call requires human attention."""

    class AlertType(models.TextChoices):
        LOW_CONFIDENCE   = 'low_confidence',   'Low AI Confidence'
        NO_ANSWER        = 'no_answer',        'No Answer Found'
        HUMAN_REQUESTED  = 'human_requested',  'Human Agent Requested'
        DROPPED_CALL     = 'dropped_call',     'Call Dropped'
        REPEATED_FAILURE = 'repeated_failure', 'Repeated Failed Interaction'
        UNRESOLVED       = 'unresolved',       'Call Unresolved'
        CALL_COMPLETED   = 'call_completed',   'Call Completed'

    class Severity(models.TextChoices):
        HIGH   = 'high',   'High'
        MEDIUM = 'medium', 'Medium'
        LOW    = 'low',    'Low'

    class Status(models.TextChoices):
        OPEN         = 'open',         'Open'
        ACKNOWLEDGED = 'acknowledged', 'Acknowledged'
        RESOLVED     = 'resolved',     'Resolved'
        DISMISSED    = 'dismissed',    'Dismissed'

    # FK to CallSession — nullable so alerts can be created standalone
    session = models.ForeignKey(
        'voice_calls.CallSession',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='alerts',
    )
    alert_type  = models.CharField(max_length=32, choices=AlertType.choices, db_index=True)
    severity    = models.CharField(max_length=8,  choices=Severity.choices, default=Severity.MEDIUM, db_index=True)
    status      = models.CharField(max_length=16, choices=Status.choices,  default=Status.OPEN, db_index=True)
    title       = models.CharField(max_length=256)
    description = models.TextField(blank=True)

    assigned_to = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_alerts',
    )
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Email delivery tracking
    send_email    = models.BooleanField(default=False)
    email_sent    = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'portal_alerts'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'created_at'], name='idx_alert_status_created'),
            models.Index(fields=['alert_type', 'status'],  name='idx_alert_type_status'),
        ]
        verbose_name = 'Alert'
        verbose_name_plural = 'Alerts'

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title} ({self.status})"


class FollowUp(TimeStampedModel):
    """Human follow-up task linked to a call session."""

    class Status(models.TextChoices):
        PENDING     = 'pending',     'Pending'
        IN_PROGRESS = 'in_progress', 'In Progress'
        COMPLETED   = 'completed',   'Completed'
        CANCELLED   = 'cancelled',   'Cancelled'
        ASSIGNED    = 'assigned',    'Assigned'
        RESOLVED    = 'resolved',    'Resolved'
        CLOSED      = 'closed',      'Closed'

    class Priority(models.TextChoices):
        URGENT = 'urgent', 'Urgent'
        HIGH   = 'high',   'High'
        MEDIUM = 'medium', 'Medium'
        LOW    = 'low',    'Low'

    session = models.ForeignKey(
        'voice_calls.CallSession',
        on_delete=models.CASCADE,
        related_name='followups',
    )
    alert = models.ForeignKey(
        Alert, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='followups',
    )
    status   = models.CharField(max_length=16, choices=Status.choices,   default=Status.PENDING,  db_index=True)
    priority = models.CharField(max_length=8,  choices=Priority.choices, default=Priority.MEDIUM, db_index=True)

    assigned_to  = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='assigned_followups',
    )
    notes        = models.TextField(blank=True)
    due_date     = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    # SLA tracking
    sla_deadline  = models.DateTimeField(null=True, blank=True, db_index=True)
    sla_breached  = models.BooleanField(default=False, db_index=True)
    reminded_at   = models.DateTimeField(null=True, blank=True)
    # Source of this follow-up
    source = models.CharField(
        max_length=20,
        choices=[
            ('rag_failure',    'RAG Failure'),
            ('human_request',  'Human Request'),
            ('unresolved',     'Unresolved Call'),
            ('manual',         'Manual'),
            ('sla_breach',     'SLA Breach'),
        ],
        default='manual',
        db_index=True,
    )

    SLA_HOURS = {
        'urgent': 1,
        'high':   4,
        'medium': 12,
        'low':    24,
    }

    @staticmethod
    def sla_hours_for(priority: str) -> int:
        return FollowUp.SLA_HOURS.get(priority, 24)

    def save(self, *args, **kwargs):
        # Auto-set SLA deadline on first save
        if not self.sla_deadline and self.priority:
            from django.utils.timezone import now
            from datetime import timedelta
            hours = FollowUp.sla_hours_for(self.priority)
            self.sla_deadline = now() + timedelta(hours=hours)
        super().save(*args, **kwargs)

    class Meta:
        db_table = 'portal_followups'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'priority'], name='idx_followup_status_priority'),
        ]
        verbose_name = 'Follow-up'
        verbose_name_plural = 'Follow-ups'

    def __str__(self):
        return f"FollowUp [{self.priority}/{self.status}] session={self.session_id}"


class NotificationPreference(models.Model):
    """Per-user notification settings (one-to-one)."""

    user          = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_pref')
    email_enabled = models.BooleanField(default=True)
    # JSON list of AlertType values the user wants notified about.
    # Empty list means all types.
    notify_on     = models.JSONField(default=list)
    # Override delivery email; falls back to user.email if blank
    notify_email  = models.EmailField(blank=True)

    # Send an email for every completed call, not just alerts/follow-ups
    notify_all_calls = models.BooleanField(default=False)

    # Future channel stubs — stored now, not yet functional
    sms_enabled      = models.BooleanField(default=False)
    sms_number       = models.CharField(max_length=32, blank=True)
    whatsapp_enabled = models.BooleanField(default=False)
    whatsapp_number  = models.CharField(max_length=32, blank=True)

    class Meta:
        db_table = 'portal_notification_preferences'
        verbose_name = 'Notification Preference'
        verbose_name_plural = 'Notification Preferences'

    def __str__(self):
        return f"NotifPref for {self.user.username}"


class CallPrompt(models.Model):
    """
    A configurable voice prompt used in the Asterisk call flow.
    Text is the source of truth; audio_path points to the generated WAV file.
    Editing text and clicking Regenerate will update the audio via OpenAI TTS.
    """
    stem       = models.CharField(max_length=64, unique=True, db_index=True)
    language   = models.CharField(max_length=8, default='en')
    text       = models.TextField()
    audio_path = models.CharField(max_length=512, blank=True)
    audio_exists = models.BooleanField(default=False)
    version    = models.PositiveIntegerField(default=1)
    enabled    = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'portal_call_prompts'
        ordering = ['stem']
        verbose_name = 'Call Prompt'
        verbose_name_plural = 'Call Prompts'

    def __str__(self):
        return f"[{self.language}] {self.stem} (v{self.version})"


class FollowUpActivity(models.Model):
    """Activity log for a FollowUp — every action is recorded here."""

    id         = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    followup   = models.ForeignKey(
        FollowUp, on_delete=models.CASCADE, related_name='activities'
    )
    user       = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='followup_activities',
    )
    action     = models.CharField(
        max_length=64,
        choices=[
            ('assigned',       'Assigned'),
            ('reassigned',     'Reassigned'),
            ('claimed',        'Claimed'),
            ('status_changed', 'Status Changed'),
            ('note_added',     'Note Added'),
            ('escalated',      'Escalated'),
            ('resolved',       'Resolved'),
            ('closed',         'Closed'),
        ],
    )
    description = models.TextField(blank=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'portal_followup_activities'
        ordering = ['-created_at']
        verbose_name = 'Follow-up Activity'
        verbose_name_plural = 'Follow-up Activities'

    def __str__(self):
        return f"[{self.action}] on followup={self.followup_id} by {self.user_id}"


class SiteConfig(models.Model):
    """
    Singleton site-wide configuration.

    Always use SiteConfig.get_solo() — never instantiate directly.
    Enforced singleton: save() always writes to pk=1.
    """

    company_name  = models.CharField(max_length=128, default='Future Smart Support')
    product_name  = models.CharField(max_length=128, default='VoiceGate AI')
    contact_email = models.EmailField(blank=True)
    gsm           = models.CharField(max_length=32, blank=True)
    website       = models.CharField(max_length=256, blank=True)
    office_hours  = models.CharField(
        max_length=256,
        default='Sunday to Thursday, 9:00 AM to 5:00 PM',
    )
    primary_color = models.CharField(max_length=16, default='#1a56db')
    accent_color  = models.CharField(max_length=16, default='#7e3af2')
    notify_all_calls = models.BooleanField(
        default=False,
        help_text='Send an email notification for every completed call site-wide.',
    )
    follow_up_emails = models.JSONField(
        default=list,
        blank=True,
        help_text='JSON list of email addresses that receive follow-up notifications.',
    )

    class Meta:
        db_table = 'portal_site_config'
        verbose_name = 'Site Configuration'
        verbose_name_plural = 'Site Configuration'

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        pass  # prevent deletion of the singleton

    @classmethod
    def get_solo(cls) -> 'SiteConfig':
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Site Config — {self.company_name}"
