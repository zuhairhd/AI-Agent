from django.contrib import admin
from django.utils.html import format_html
from .models import CallRecord, CallEvent, CallSession, ConversationTurn


# ---------------------------------------------------------------------------
# Legacy single-turn models
# ---------------------------------------------------------------------------

class CallEventInline(admin.TabularInline):
    model = CallEvent
    extra = 0
    readonly_fields = ('id', 'event_type', 'payload', 'created_at')
    fields = ('event_type', 'payload', 'created_at')
    ordering = ('created_at',)
    can_delete = False


@admin.register(CallRecord)
class CallRecordAdmin(admin.ModelAdmin):
    list_display = (
        'caller_number', 'status_badge', 'created_at',
        'answered_at', 'has_transcript', 'has_response', 'has_audio',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('caller_number', 'transcript_text')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'answered_at', 'status',
        'transcript_text', 'gpt_response_text', 'response_audio_path',
    )
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
        ('Audio Output', {
            'fields': ('response_audio_path',),
            'classes': ('collapse',),
        }),
    )

    def status_badge(self, obj):
        colors = {
            'pending':     '#f59e0b',
            'processing':  '#3b82f6',
            'answered':    '#10b981',
            'audio_ready': '#6366f1',
            'failed':      '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.status.upper(),
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

    def has_audio(self, obj):
        return bool(obj.response_audio_path)
    has_audio.boolean = True
    has_audio.short_description = 'Audio'


@admin.register(CallEvent)
class CallEventAdmin(admin.ModelAdmin):
    list_display = ('call', 'event_type', 'created_at')
    list_filter = ('event_type',)
    readonly_fields = ('id', 'call', 'event_type', 'payload', 'created_at')
    ordering = ('-created_at',)
    list_per_page = 50


# ---------------------------------------------------------------------------
# Multi-turn session models
# ---------------------------------------------------------------------------

class ConversationTurnInline(admin.TabularInline):
    model = ConversationTurn
    extra = 0
    readonly_fields = (
        'id', 'turn_number', 'status', 'transcript_text',
        'ai_response_text', 'audio_response_path', 'transfer_needed',
        'transfer_reason', 'error_message', 'created_at',
    )
    fields = (
        'turn_number', 'status', 'transcript_text',
        'ai_response_text', 'has_audio_col', 'transfer_needed', 'error_message',
    )
    ordering = ('turn_number',)
    can_delete = False

    def has_audio_col(self, obj):
        return bool(obj.audio_response_path)
    has_audio_col.boolean = True
    has_audio_col.short_description = 'Audio'


@admin.register(CallSession)
class CallSessionAdmin(admin.ModelAdmin):
    list_display = (
        'caller_number', 'session_status_badge', 'total_turns',
        'started_at', 'ended_at', 'transfer_triggered',
    )
    list_filter = ('status', 'transfer_triggered', 'started_at')
    search_fields = ('caller_number', 'transfer_reason', 'failure_reason')
    readonly_fields = (
        'id', 'created_at', 'updated_at', 'started_at', 'ended_at',
        'status', 'total_turns', 'transfer_triggered', 'transfer_reason',
        'failure_reason',
    )
    ordering = ('-started_at',)
    inlines = [ConversationTurnInline]
    list_per_page = 25

    fieldsets = (
        ('Session Info', {
            'fields': (
                'id', 'caller_number', 'status', 'total_turns',
                'started_at', 'ended_at',
            ),
        }),
        ('Transfer', {
            'fields': ('transfer_triggered', 'transfer_reason'),
            'classes': ('collapse',),
        }),
        ('Failure', {
            'fields': ('failure_reason',),
            'classes': ('collapse',),
        }),
    )

    def session_status_badge(self, obj):
        colors = {
            'active':      '#3b82f6',
            'completed':   '#10b981',
            'transferred': '#f59e0b',
            'failed':      '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.status.upper(),
        )
    session_status_badge.short_description = 'Status'


@admin.register(ConversationTurn)
class ConversationTurnAdmin(admin.ModelAdmin):
    list_display = (
        'session', 'turn_number', 'turn_status_badge',
        'has_transcript', 'has_response', 'has_audio', 'transfer_needed', 'created_at',
    )
    list_filter = ('status', 'transfer_needed', 'created_at')
    search_fields = ('session__caller_number', 'transcript_text', 'ai_response_text')
    readonly_fields = (
        'id', 'session', 'turn_number', 'status',
        'audio_input_path', 'audio_input_exists', 'audio_input_size',
        'transcript_text', 'transcription_started_at', 'transcription_completed_at',
        'ai_response_text', 'llm_started_at', 'llm_completed_at',
        'audio_response_path', 'audio_response_exists', 'audio_response_size',
        'tts_started_at', 'tts_completed_at',
        'transfer_needed', 'transfer_reason', 'error_message', 'created_at',
    )
    ordering = ('-created_at',)
    list_per_page = 50

    fieldsets = (
        ('Turn Info', {
            'fields': ('id', 'session', 'turn_number', 'status', 'created_at'),
        }),
        ('Input Audio', {
            'fields': ('audio_input_path', 'audio_input_exists', 'audio_input_size'),
        }),
        ('Transcription', {
            'fields': ('transcript_text', 'transcription_started_at', 'transcription_completed_at'),
            'classes': ('collapse',),
        }),
        ('AI Response', {
            'fields': ('ai_response_text', 'llm_started_at', 'llm_completed_at'),
            'classes': ('collapse',),
        }),
        ('Output Audio', {
            'fields': (
                'audio_response_path', 'audio_response_exists', 'audio_response_size',
                'tts_started_at', 'tts_completed_at',
            ),
            'classes': ('collapse',),
        }),
        ('Transfer & Errors', {
            'fields': ('transfer_needed', 'transfer_reason', 'error_message'),
            'classes': ('collapse',),
        }),
    )

    def turn_status_badge(self, obj):
        colors = {
            'pending':    '#f59e0b',
            'processing': '#3b82f6',
            'ready':      '#10b981',
            'failed':     '#ef4444',
        }
        color = colors.get(obj.status, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;'
            'border-radius:12px;font-size:11px;font-weight:600;">{}</span>',
            color, obj.status.upper(),
        )
    turn_status_badge.short_description = 'Status'

    def has_transcript(self, obj):
        return bool(obj.transcript_text)
    has_transcript.boolean = True
    has_transcript.short_description = 'STT'

    def has_response(self, obj):
        return bool(obj.ai_response_text)
    has_response.boolean = True
    has_response.short_description = 'LLM'

    def has_audio(self, obj):
        return bool(obj.audio_response_path)
    has_audio.boolean = True
    has_audio.short_description = 'Audio'
