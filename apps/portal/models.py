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

    class Priority(models.TextChoices):
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
