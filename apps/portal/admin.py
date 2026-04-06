from django.contrib import admin
from .models import Alert, FollowUp, NotificationPreference


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display  = ('title', 'alert_type', 'severity', 'status', 'send_email', 'email_sent', 'created_at')
    list_filter   = ('alert_type', 'severity', 'status', 'send_email', 'email_sent')
    search_fields = ('title', 'description', 'session__caller_number')
    readonly_fields = ('email_sent', 'email_sent_at', 'created_at', 'updated_at')


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display  = ('session', 'status', 'priority', 'assigned_to', 'due_date', 'created_at')
    list_filter   = ('status', 'priority')
    search_fields = ('session__caller_number', 'notes')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    list_display  = ('user', 'email_enabled', 'sms_enabled', 'whatsapp_enabled')
    search_fields = ('user__username', 'user__email', 'notify_email')
