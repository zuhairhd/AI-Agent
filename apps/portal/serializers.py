from django.contrib.auth import get_user_model
from rest_framework import serializers
from apps.voice_calls.models import CallSession, ConversationTurn
from .models import Alert, FollowUp, NotificationPreference, CallPrompt, FollowUpActivity

User = get_user_model()


class UserBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ('id', 'username', 'email', 'first_name', 'last_name')


class ConversationTurnSerializer(serializers.ModelSerializer):
    class Meta:
        model  = ConversationTurn
        fields = (
            'id', 'turn_number', 'status',
            'audio_input_path', 'transcript_text',
            'ai_response_text', 'ai_confidence_score',
            'audio_response_path', 'audio_response_exists',
            'transfer_needed', 'transfer_reason',
            'closing_detected', 'rag_failure',
            'error_message',
            'transcription_started_at', 'transcription_completed_at',
            'llm_started_at', 'llm_completed_at',
            'tts_started_at', 'tts_completed_at',
            'created_at',
        )


class CallSessionListSerializer(serializers.ModelSerializer):
    avg_confidence = serializers.SerializerMethodField()

    class Meta:
        model  = CallSession
        fields = (
            'id', 'caller_number', 'started_at', 'ended_at', 'status',
            'language', 'total_turns', 'transfer_triggered',
            'needs_followup', 'duration_seconds', 'avg_confidence',
        )

    def get_avg_confidence(self, obj):
        scores = [
            t.ai_confidence_score
            for t in obj.turns.all()
            if t.ai_confidence_score is not None
        ]
        return round(sum(scores) / len(scores), 3) if scores else None


class CallSessionDetailSerializer(CallSessionListSerializer):
    turns = ConversationTurnSerializer(many=True, read_only=True)

    class Meta(CallSessionListSerializer.Meta):
        fields = CallSessionListSerializer.Meta.fields + (
            'turns', 'failure_reason', 'transfer_reason',
            'staff_notes', 'created_at', 'updated_at',
        )


class AlertSerializer(serializers.ModelSerializer):
    session_caller = serializers.SerializerMethodField()
    assigned_to    = UserBriefSerializer(read_only=True)

    class Meta:
        model  = Alert
        fields = (
            'id', 'alert_type', 'severity', 'status', 'title', 'description',
            'session', 'session_caller',
            'assigned_to', 'resolved_at',
            'send_email', 'email_sent', 'email_sent_at',
            'created_at', 'updated_at',
        )
        read_only_fields = ('email_sent', 'email_sent_at', 'created_at', 'updated_at')

    def get_session_caller(self, obj):
        return obj.session.caller_number if obj.session else None


class FollowUpActivitySerializer(serializers.ModelSerializer):
    user = UserBriefSerializer(read_only=True)

    class Meta:
        model  = FollowUpActivity
        fields = ('id', 'action', 'description', 'user', 'created_at')


class FollowUpSerializer(serializers.ModelSerializer):
    assigned_to    = UserBriefSerializer(read_only=True)
    session_caller = serializers.SerializerMethodField()
    sla_pct        = serializers.SerializerMethodField()
    sla_remaining  = serializers.SerializerMethodField()
    activities     = FollowUpActivitySerializer(many=True, read_only=True)

    class Meta:
        model  = FollowUp
        fields = (
            'id', 'session', 'session_caller', 'alert',
            'status', 'priority', 'source', 'assigned_to',
            'notes', 'due_date', 'completed_at',
            'sla_deadline', 'sla_breached', 'sla_pct', 'sla_remaining',
            'activities',
            'created_at', 'updated_at',
        )

    def get_session_caller(self, obj):
        return obj.session.caller_number if obj.session else None

    def get_sla_pct(self, obj):
        if not obj.sla_deadline or not obj.created_at:
            return None
        from django.utils.timezone import now
        total   = (obj.sla_deadline - obj.created_at).total_seconds()
        elapsed = (now() - obj.created_at).total_seconds()
        return min(round(elapsed / total * 100, 1), 100) if total > 0 else 100

    def get_sla_remaining(self, obj):
        if not obj.sla_deadline:
            return None
        from django.utils.timezone import now
        remaining = (obj.sla_deadline - now()).total_seconds()
        return max(round(remaining), 0)


class CallPromptSerializer(serializers.ModelSerializer):
    class Meta:
        model  = CallPrompt
        fields = ('id', 'stem', 'language', 'text', 'audio_path', 'audio_exists',
                  'version', 'enabled', 'updated_at')
        read_only_fields = ('audio_exists', 'version', 'updated_at')


class NotificationPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model  = NotificationPreference
        fields = (
            'email_enabled', 'notify_on', 'notify_email',
            'sms_enabled', 'sms_number',
            'whatsapp_enabled', 'whatsapp_number',
        )
