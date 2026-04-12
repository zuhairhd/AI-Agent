from django.contrib import admin
from .models import Alert, FollowUp, NotificationPreference, CallPrompt, FollowUpActivity, SiteConfig


@admin.register(Alert)
class AlertAdmin(admin.ModelAdmin):
    list_display   = ('title', 'alert_type', 'severity', 'status', 'send_email', 'email_sent', 'created_at')
    list_filter    = ('alert_type', 'severity', 'status', 'send_email', 'email_sent')
    search_fields  = ('title', 'description', 'session__caller_number')
    readonly_fields = ('email_sent', 'email_sent_at', 'created_at', 'updated_at')


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display  = ('session', 'status', 'priority', 'source', 'sla_breached', 'sla_deadline', 'assigned_to', 'created_at')
    list_filter   = ('status', 'priority', 'source', 'sla_breached')
    search_fields = ('session__caller_number', 'notes')


@admin.register(FollowUpActivity)
class FollowUpActivityAdmin(admin.ModelAdmin):
    list_display  = ('followup', 'action', 'user', 'created_at')
    list_filter   = ('action',)
    search_fields = ('description',)


@admin.register(CallPrompt)
class CallPromptAdmin(admin.ModelAdmin):
    list_display  = ('stem', 'language', 'version', 'enabled', 'audio_exists', 'updated_at')
    list_filter   = ('language', 'enabled')
    search_fields = ('stem', 'text')


@admin.register(NotificationPreference)
class NotificationPreferenceAdmin(admin.ModelAdmin):
    """
    Per-user notification settings.

    notify_on — JSON list of alert type keys the user wants to receive.
                Leave empty (default) to receive ALL alert types.
                Valid values: low_confidence, no_answer, human_requested,
                dropped_call, repeated_failure, unresolved, call_completed

    notify_all_calls — User-level opt-in for CALL_COMPLETED emails when the
                       global SiteConfig.notify_all_calls toggle is OFF.
                       When SiteConfig.notify_all_calls=True all email-enabled
                       users already receive these; this field is only consulted
                       when the global flag is False.
    """
    list_display   = (
        'user', 'email_enabled', 'notify_email_display',
        'notify_all_calls', 'notify_on_display',
        'sms_enabled', 'whatsapp_enabled',
    )
    list_filter    = ('email_enabled', 'notify_all_calls', 'sms_enabled')
    search_fields  = ('user__username', 'user__email', 'notify_email')
    readonly_fields = ('user',)
    fieldsets = (
        ('User', {
            'fields': ('user',),
        }),
        ('Email', {
            'fields': ('email_enabled', 'notify_email', 'notify_on', 'notify_all_calls'),
            'description': (
                'notify_on: JSON list of alert types (empty = all). '
                'Valid keys: low_confidence, no_answer, human_requested, '
                'dropped_call, repeated_failure, unresolved, call_completed. '
                'notify_all_calls: receive CALL_COMPLETED emails even when the '
                'global SiteConfig.notify_all_calls is disabled.'
            ),
        }),
        ('SMS / WhatsApp (future)', {
            'classes': ('collapse',),
            'fields': ('sms_enabled', 'sms_number', 'whatsapp_enabled', 'whatsapp_number'),
        }),
    )

    @admin.display(description='Notify email')
    def notify_email_display(self, obj):
        return obj.notify_email or obj.user.email or '—'

    @admin.display(description='Notify on (types)')
    def notify_on_display(self, obj):
        if not obj.notify_on:
            return 'all'
        return ', '.join(obj.notify_on)


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    """
    Global site configuration — singleton (pk=1).

    Notification fields
    ───────────────────
    notify_all_calls  — When True, a CALL_COMPLETED alert is created for every
                        completed call and ALL email-enabled users receive it.
                        This is the master global switch.

    follow_up_emails  — JSON list of addresses that are ALWAYS CC'd on every
                        alert email, regardless of user preferences.
                        Example: ["support@example.com", "manager@example.com"]

    contact_email     — Used as a last-resort fallback recipient when no other
                        recipient can be resolved (no user prefs, no follow_up_emails).
                        Should always be set to a monitored address.
    """
    fieldsets = (
        ('Branding', {
            'fields': ('company_name', 'product_name', 'primary_color', 'accent_color'),
        }),
        ('Contact', {
            'fields': ('contact_email', 'gsm', 'website'),
            'description': 'contact_email is also used as the last-resort email fallback.',
        }),
        ('Notifications', {
            'fields': ('notify_all_calls', 'follow_up_emails'),
            'description': (
                'notify_all_calls: global on/off for completed-call emails. '
                'follow_up_emails: always-CC list for every alert email.'
            ),
        }),
        ('Operations', {
            'fields': ('office_hours',),
        }),
    )

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
