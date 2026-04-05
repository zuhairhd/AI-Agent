from django.contrib import admin
from django.utils.html import format_html
from .models import CallRecord, CallEvent


class CallEventInline(admin.TabularInline):
    model = CallEvent
    extra = 0
    readonly_fields = ('id', 'event_type', 'payload', 'created_at')
    fields = ('event_type', 'payload', 'created_at')
    ordering = ('created_at',)
    can_delete = False


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = ('caller_number', 'status_badge', 'created_at', 'answered_at', 'has_transcript', 'has_response')
    list_filter = ('status', 'created_at')
    search_fields = ('caller_number', 'transcript_text')
    readonly_fields = ('id', 'created_at', 'updated_at', 'answered_at', 'status', 'transcript_text', 'gpt_response_text')
    ordering = ('-created_at',)
    inlines = [CallEventInline]
    list_per_page = 25

    fieldsets = (
        ('Call Info', {
            'fields': ('id', 'caller_number', 'audio_file_path', 'status', 'created_at', 'answered_at'),
        }),
        ('Transcription', {
            'fields': ('transcript_text',),
            'classes': ('collapse',),
        }),
        ('AI Response', {
            'fields': ('gpt_response_text',),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending': '#f59e0b',
            'processing': '#3b82f6',
            'answered': '#10b981',
            'failed': '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.status.upper()
        )
    status_badge.short_description = 'Status'

    def has_transcript(self, obj):
        return bool(obj.transcript_text)
    has_transcript.boolean = True
    has_transcript.short_description = 'Transcript'

    def has_response(self, obj):
        return bool(obj.gpt_response_text)
    has_response.boolean = True
    has_response.short_description = 'Response'


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ('call', 'event_type', 'created_at')
    list_filter = ('event_type',)
    readonly_fields = ('id', 'call', 'event_type', 'payload', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 50
