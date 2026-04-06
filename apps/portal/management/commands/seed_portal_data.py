"""
Management command: seed_portal_data
Creates demo CallSession, ConversationTurn, Alert, and FollowUp records
so the portal UI is populated immediately on a fresh install.

Usage:
    python manage.py seed_portal_data
    python manage.py seed_portal_data --force   (drop existing demo data first)
"""
import uuid
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils.timezone import now

User = get_user_model()


class Command(BaseCommand):
    help = 'Seed demo data for the FSS Admin Portal.'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true', help='Delete existing demo data first')

    def handle(self, *args, **options):
        from apps.voice_calls.models import CallSession, ConversationTurn
        from apps.portal.models import Alert, FollowUp

        if options['force']:
            self.stdout.write('Deleting existing demo sessions…')
            CallSession.objects.filter(caller_number__startswith='+9665500').delete()

        if CallSession.objects.filter(caller_number__startswith='+9665500').exists():
            self.stdout.write(self.style.WARNING('Demo data already exists. Use --force to regenerate.'))
            return

        self.stdout.write('Creating demo call sessions…')
        sessions_data = [
            dict(caller='+966550011111', status='completed', turns=2,  language='ar', transfer=False, followup=False),
            dict(caller='+966550022222', status='failed',    turns=0,  language='en', transfer=False, followup=True),
            dict(caller='+966550033333', status='completed', turns=3,  language='en', transfer=True,  followup=True),
            dict(caller='+966550044444', status='completed', turns=1,  language='ar', transfer=False, followup=False),
            dict(caller='+966550055555', status='failed',    turns=0,  language='en', transfer=False, followup=True),
        ]

        for offset, sd in enumerate(sessions_data):
            started = now() - timedelta(hours=offset * 3 + 1)
            ended   = started + timedelta(minutes=3 + offset)

            session = CallSession.objects.create(
                id=uuid.uuid4(),
                caller_number=sd['caller'],
                started_at=started,
                ended_at=ended if sd['status'] != 'active' else None,
                status=sd['status'],
                language=sd['language'],
                transfer_triggered=sd['transfer'],
                transfer_reason='Caller requested human agent' if sd['transfer'] else '',
                needs_followup=sd['followup'],
                total_turns=sd['turns'],
                failure_reason='Connection lost' if sd['status'] == 'failed' else '',
            )

            # Conversation turns
            for t in range(sd['turns']):
                ConversationTurn.objects.create(
                    id=uuid.uuid4(),
                    session=session,
                    turn_number=t + 1,
                    status='ready',
                    audio_input_path=f'/var/spool/asterisk/monitor/{session.id}_turn{t+1}.wav',
                    audio_input_exists=True,
                    audio_input_size=48000,
                    transcript_text='مرحبا، أريد الاستفسار عن ساعات العمل.' if sd['language'] == 'ar'
                                    else 'Hello, I want to ask about office hours.',
                    ai_response_text='ساعات العمل: صباحاً 9-1، مساءً 4-7.' if sd['language'] == 'ar'
                                     else 'Office hours are: Morning 9 AM–1 PM, Evening 4 PM–7 PM.',
                    ai_confidence_score=0.85 - (t * 0.05),
                    audio_response_path=f'/home/agent/voice_ai_agent/media/call_responses/{session.id}_turn{t+1}.wav',
                    audio_response_exists=True,
                    audio_response_size=64000,
                    transfer_needed=sd['transfer'] and t == sd['turns'] - 1,
                )

            # Signals will create alerts, but let's also create one explicitly for demo
            if sd['status'] == 'failed':
                Alert.objects.get_or_create(
                    session=session,
                    alert_type=Alert.AlertType.DROPPED_CALL,
                    defaults=dict(
                        severity=Alert.Severity.HIGH,
                        title=f'Call dropped — {sd["caller"]}',
                        description='Demo: session ended with failed status.',
                        send_email=True,
                        status=Alert.Status.OPEN,
                    ),
                )

            if sd['followup']:
                followup, _ = FollowUp.objects.get_or_create(
                    session=session,
                    defaults=dict(
                        status=FollowUp.Status.PENDING,
                        priority=FollowUp.Priority.HIGH,
                        notes='Callback required — caller did not get a satisfactory answer.',
                    ),
                )

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {len(sessions_data)} demo call sessions with turns, alerts, and follow-ups.'
        ))
