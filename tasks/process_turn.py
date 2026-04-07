"""
Celery task: process one ConversationTurn of a multi-turn call session.

Pipeline per turn:
  1. Load ConversationTurn and audit input audio file.
  2. Transcribe caller audio via Whisper (STT).
  3. Build conversation history from previous turns.
  4. Call LLM service (RAG + hybrid transfer + closing + no-answer detection).
  5. Synthesise AI reply to Asterisk-compatible WAV (TTS).
  6. Audit output audio file.
  7. Persist all results; update CallSession.
  8. If RAG failure → create FollowUp + Alert.
  9. If closing detected → finalize session.
"""
import logging
import os

from celery import shared_task
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.voice_calls.models import CallSession, ConversationTurn

logger = logging.getLogger(__name__)


def _build_history(session: CallSession) -> list:
    turns = (
        session.turns
        .filter(status=ConversationTurn.Status.READY)
        .order_by('turn_number')
    )
    history = []
    for t in turns:
        if t.transcript_text:
            history.append({'role': 'user', 'content': t.transcript_text})
        if t.ai_response_text:
            history.append({'role': 'assistant', 'content': t.ai_response_text})
    return history[-20:]


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60,
    name='tasks.process_turn',
)
def process_turn(self, turn_id: str) -> dict:
    logger.info(f"[process_turn] start | turn={turn_id}")

    try:
        turn = ConversationTurn.objects.select_related('session').get(id=turn_id)
    except ConversationTurn.DoesNotExist:
        logger.error(f"[process_turn] turn not found: {turn_id}")
        return {'status': 'error', 'reason': 'turn_not_found'}

    session = turn.session

    turn.status = ConversationTurn.Status.PROCESSING
    turn.save(update_fields=['status'])

    # ── Audit input audio ──────────────────────────────────────────────────
    input_path   = turn.audio_input_path
    input_exists = os.path.isfile(input_path)
    input_size   = os.path.getsize(input_path) if input_exists else None
    turn.audio_input_exists = input_exists
    turn.audio_input_size   = input_size
    turn.save(update_fields=['audio_input_exists', 'audio_input_size'])

    logger.info(
        f"[process_turn] input_audio | turn={turn_id} "
        f"exists={input_exists} size={input_size} path={input_path}"
    )

    if not input_exists:
        _fail(turn, session, f"Input audio file not found: {input_path}")
        return {'status': 'failed', 'reason': 'input_audio_missing', 'turn_id': turn_id}

    # ── STT ────────────────────────────────────────────────────────────────
    from services.openai_transcription_service import transcribe

    turn.transcription_started_at = timezone.now()
    turn.save(update_fields=['transcription_started_at'])

    try:
        transcript = transcribe(input_path)
    except Exception as exc:
        logger.error(f"[process_turn] STT failed | turn={turn_id}: {exc}", exc_info=True)
        _fail(turn, session, f"Transcription failed: {exc}")
        raise

    turn.transcript_text            = transcript
    turn.transcription_completed_at = timezone.now()
    turn.save(update_fields=['transcript_text', 'transcription_completed_at'])
    logger.info(f"[process_turn] STT done | turn={turn_id} len={len(transcript)}")

    # ── LLM ────────────────────────────────────────────────────────────────
    from services.llm_service import process_turn as llm_process_turn

    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', '')
    history         = _build_history(session)

    turn.llm_started_at = timezone.now()
    turn.save(update_fields=['llm_started_at'])

    try:
        result = llm_process_turn(
            question=transcript,
            history=history,
            vector_store_id=vector_store_id,
            language=session.language,
        )
    except Exception as exc:
        logger.error(f"[process_turn] LLM failed | turn={turn_id}: {exc}", exc_info=True)
        _fail(turn, session, f"LLM failed: {exc}")
        raise

    answer_text     = result['answer']
    needs_transfer  = result['transfer']
    transfer_reason = result.get('reason', '')
    closing         = result.get('closing', False)
    rag_no_answer   = result.get('rag_no_answer', False)

    turn.ai_response_text  = answer_text
    turn.llm_completed_at  = timezone.now()
    turn.transfer_needed   = needs_transfer
    turn.transfer_reason   = transfer_reason
    turn.closing_detected  = closing
    turn.rag_failure       = rag_no_answer
    turn.save(update_fields=[
        'ai_response_text', 'llm_completed_at',
        'transfer_needed', 'transfer_reason',
        'closing_detected', 'rag_failure',
    ])

    logger.info(
        f"[process_turn] LLM done | turn={turn_id} "
        f"reply_len={len(answer_text)} transfer={needs_transfer} "
        f"closing={closing} rag_no_answer={rag_no_answer}"
    )

    # ── TTS ────────────────────────────────────────────────────────────────
    from services.openai_tts_service import synthesise

    turn.tts_started_at = timezone.now()
    turn.save(update_fields=['tts_started_at'])

    try:
        audio_path = synthesise(text=answer_text, turn_id=str(turn_id))
    except Exception as exc:
        logger.error(f"[process_turn] TTS failed | turn={turn_id}: {exc}", exc_info=True)
        turn.error_message   = f"TTS failed: {exc}"
        turn.tts_completed_at = timezone.now()
        turn.status           = ConversationTurn.Status.FAILED
        turn.save(update_fields=['error_message', 'tts_completed_at', 'status'])
        if needs_transfer:
            _trigger_session_transfer(session, transfer_reason)
        return {
            'status':   'failed',
            'stage':    'tts',
            'turn_id':  turn_id,
            'transfer': needs_transfer,
        }

    # ── Audit output audio ──────────────────────────────────────────────────
    out_exists = os.path.isfile(audio_path)
    out_size   = os.path.getsize(audio_path) if out_exists else None

    turn.audio_response_path   = audio_path
    turn.audio_response_exists = out_exists
    turn.audio_response_size   = out_size
    turn.tts_completed_at      = timezone.now()
    turn.status                = ConversationTurn.Status.READY
    turn.save(update_fields=[
        'audio_response_path', 'audio_response_exists', 'audio_response_size',
        'tts_completed_at', 'status',
    ])

    logger.info(
        f"[process_turn] TTS done | turn={turn_id} "
        f"path={audio_path} exists={out_exists} size={out_size}"
    )

    # ── Update session turn count ───────────────────────────────────────────
    _increment_session_turns(session)

    # ── RAG failure handling ────────────────────────────────────────────────
    if rag_no_answer:
        _handle_rag_failure(session, turn, transcript)

    # ── Transfer or closing ─────────────────────────────────────────────────
    if needs_transfer:
        _trigger_session_transfer(session, transfer_reason)
        logger.info(f"[process_turn] transfer triggered | session={session.id}")

    if closing and not needs_transfer:
        _finalize_session(session, CallSession.Status.COMPLETED)
        logger.info(f"[process_turn] closing detected — session finalized | session={session.id}")

    return {
        'status':          'ready',
        'turn_id':         turn_id,
        'session_id':      str(session.id),
        'audio_path':      audio_path,
        'transfer':        needs_transfer,
        'transfer_reason': transfer_reason,
        'closing':         closing,
        'rag_no_answer':   rag_no_answer,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fail(turn: ConversationTurn, session: CallSession, reason: str) -> None:
    turn.status        = ConversationTurn.Status.FAILED
    turn.error_message = reason
    turn.save(update_fields=['status', 'error_message'])
    logger.error(f"[process_turn] FAILED | turn={turn.id} reason={reason}")


def _increment_session_turns(session: CallSession) -> None:
    CallSession.objects.filter(pk=session.pk).update(
        total_turns=F('total_turns') + 1,
    )


def _trigger_session_transfer(session: CallSession, reason: str) -> None:
    from django.utils import timezone
    CallSession.objects.filter(pk=session.pk).update(
        transfer_triggered=True,
        transfer_reason=reason,
        status=CallSession.Status.TRANSFERRED,
        ended_at=timezone.now(),
    )


def _finalize_session(session: CallSession, status: str) -> None:
    from django.utils import timezone
    ended = timezone.now()
    duration = int((ended - session.started_at).total_seconds())
    CallSession.objects.filter(pk=session.pk).update(
        status=status,
        ended_at=ended,
        duration_seconds=duration,
    )


def _handle_rag_failure(session: CallSession, turn: ConversationTurn, question: str) -> None:
    """
    When RAG cannot answer:
    1. Set session needs_followup = True.
    2. Create a FollowUp record.
    3. Create an Alert and queue email notification.
    """
    try:
        from apps.portal.models import Alert, FollowUp
        from apps.portal.tasks import send_alert_notification

        # Mark session for follow-up
        CallSession.objects.filter(pk=session.pk).update(needs_followup=True)

        # Create alert (idempotent — one per session per type)
        alert, created = Alert.objects.get_or_create(
            session=session,
            alert_type=Alert.AlertType.NO_ANSWER,
            defaults=dict(
                severity=Alert.Severity.MEDIUM,
                title=f"RAG failure — {session.caller_number}",
                description=(
                    f"AI could not find a reliable answer from the knowledge base.\n"
                    f"Caller question: {question[:200]}"
                ),
                send_email=True,
            ),
        )

        # Create follow-up
        if not session.followups.filter(source='rag_failure').exists():
            FollowUp.objects.create(
                session=session,
                alert=alert,
                status=FollowUp.Status.PENDING,
                priority=FollowUp.Priority.MEDIUM,
                source='rag_failure',
                notes=(
                    "AI could not find a reliable answer from the knowledge base.\n"
                    f"Caller question: {question[:200]}"
                ),
            )

        if created:
            send_alert_notification.delay(str(alert.id))

        logger.info(
            f"[process_turn] RAG failure handled | session={session.id} "
            f"alert_created={created}"
        )
    except Exception as exc:
        logger.error(f"[process_turn] RAG failure handler error: {exc}", exc_info=True)
