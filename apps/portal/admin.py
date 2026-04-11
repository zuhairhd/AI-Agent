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
    list_display  = ('user', 'email_enabled', 'sms_enabled', 'whatsapp_enabled')
    search_fields = ('user__username', 'user__email', 'notify_email')


@admin.register(SiteConfig)
class SiteConfigAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Branding', {
            'fields': ('company_name', 'product_name', 'primary_color', 'accent_color'),
        }),
        ('Contact', {
            'fields': ('contact_email', 'gsm', 'website'),
        }),
        ('Operations', {
            'fields': ('office_hours', 'notify_all_calls', 'follow_up_emails'),
        }),
    )

    def has_add_permission(self, request):
        return not SiteConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
