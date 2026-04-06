"""
Celery task: process one ConversationTurn of a multi-turn call session.

Pipeline per turn:
  1. Load ConversationTurn and audit input audio file.
  2. Transcribe caller audio via Whisper (STT).
  3. Build conversation history from previous turns.
  4. Call LLM service (RAG + hybrid transfer detection).
  5. Synthesise AI reply to Asterisk-compatible WAV (TTS).
  6. Audit output audio file.
  7. Persist all results; update CallSession.
"""
import logging
import os

from celery import shared_task
from django.conf import settings
from django.db.models import F
from django.utils import timezone

from apps.voice_calls.models import CallSession, ConversationTurn

logger = logging.getLogger(__name__)


def _build_history(session: CallSession) -> list[dict]:
    """
    Return OpenAI message-style history for all completed turns in this session,
    ordered by turn_number. Capped at last 10 turns to control token usage.
    """
    turns = (
        session.turns
        .filter(status=ConversationTurn.Status.READY)
        .order_by('turn_number')
    )
    history: list[dict] = []
    for t in turns:
        if t.transcript_text:
            history.append({'role': 'user', 'content': t.transcript_text})
        if t.ai_response_text:
            history.append({'role': 'assistant', 'content': t.ai_response_text})
    return history[-20:]  # 10 user + 10 assistant


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60,
    name='tasks.process_turn',
)
def process_turn(self, turn_id: str) -> dict:
    """
    Process a single ConversationTurn.

    Returns a dict with the turn outcome so Celery stores it in the result
    backend and the AGI polling loop can see the final state.
    """
    logger.info(f"[process_turn] start | turn={turn_id}")

    # ── Load turn ─────────────────────────────────────────────────────────
    try:
        turn = ConversationTurn.objects.select_related('session').get(id=turn_id)
    except ConversationTurn.DoesNotExist:
        logger.error(f"[process_turn] turn not found: {turn_id}")
        return {'status': 'error', 'reason': 'turn_not_found'}

    session = turn.session

    # ── Mark processing ────────────────────────────────────────────────────
    turn.status = ConversationTurn.Status.PROCESSING
    turn.save(update_fields=['status'])

    # ── Audit input audio ──────────────────────────────────────────────────
    input_path = turn.audio_input_path
    input_exists = os.path.isfile(input_path)
    input_size = os.path.getsize(input_path) if input_exists else None
    turn.audio_input_exists = input_exists
    turn.audio_input_size = input_size
    turn.save(update_fields=['audio_input_exists', 'audio_input_size'])

    logger.info(
        f"[process_turn] input_audio | turn={turn_id} "
        f"exists={input_exists} size={input_size} path={input_path}"
    )

    if not input_exists:
        _fail(turn, session, f"Input audio file not found: {input_path}")
        return {'status': 'failed', 'reason': 'input_audio_missing', 'turn_id': turn_id}

    # ── STT: Transcription ─────────────────────────────────────────────────
    from services.openai_transcription_service import transcribe

    turn.transcription_started_at = timezone.now()
    turn.save(update_fields=['transcription_started_at'])

    try:
        transcript = transcribe(input_path)
    except Exception as exc:
        logger.error(f"[process_turn] STT failed | turn={turn_id}: {exc}", exc_info=True)
        _fail(turn, session, f"Transcription failed: {exc}")
        raise  # trigger autoretry

    turn.transcript_text = transcript
    turn.transcription_completed_at = timezone.now()
    turn.save(update_fields=['transcript_text', 'transcription_completed_at'])
    logger.info(f"[process_turn] STT done | turn={turn_id} len={len(transcript)}")

    # ── LLM: Generate reply with hybrid transfer detection ─────────────────
    from services.llm_service import process_turn as llm_process_turn

    vector_store_id = getattr(settings, 'OPENAI_VECTOR_STORE_ID', '')
    history = _build_history(session)

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

    answer_text = result['answer']
    needs_transfer = result['transfer']
    transfer_reason = result.get('reason', '')

    turn.ai_response_text = answer_text
    turn.llm_completed_at = timezone.now()
    turn.transfer_needed = needs_transfer
    turn.transfer_reason = transfer_reason
    turn.save(update_fields=[
        'ai_response_text', 'llm_completed_at',
        'transfer_needed', 'transfer_reason',
    ])
    logger.info(
        f"[process_turn] LLM done | turn={turn_id} "
        f"reply_len={len(answer_text)} transfer={needs_transfer}"
    )

    # ── TTS: Convert reply to WAV ──────────────────────────────────────────
    from services.openai_tts_service import synthesise

    turn.tts_started_at = timezone.now()
    turn.save(update_fields=['tts_started_at'])

    try:
        audio_path = synthesise(text=answer_text, turn_id=str(turn_id))
    except Exception as exc:
        logger.error(f"[process_turn] TTS failed | turn={turn_id}: {exc}", exc_info=True)
        # TTS failure — the LLM answer is still valid, but audio is missing.
        # Mark the turn failed; do NOT count it as a successfully completed turn.
        turn.error_message = f"TTS failed: {exc}"
        turn.tts_completed_at = timezone.now()
        turn.status = ConversationTurn.Status.FAILED
        turn.save(update_fields=['error_message', 'tts_completed_at', 'status'])
        # Still propagate transfer decision even if TTS failed.
        if needs_transfer:
            _trigger_session_transfer(session, transfer_reason)
        return {
            'status': 'failed',
            'stage': 'tts',
            'turn_id': turn_id,
            'transfer': needs_transfer,
        }

    # ── Audit output audio ─────────────────────────────────────────────────
    out_exists = os.path.isfile(audio_path)
    out_size = os.path.getsize(audio_path) if out_exists else None

    turn.audio_response_path = audio_path
    turn.audio_response_exists = out_exists
    turn.audio_response_size = out_size
    turn.tts_completed_at = timezone.now()
    turn.status = ConversationTurn.Status.READY
    turn.save(update_fields=[
        'audio_response_path', 'audio_response_exists', 'audio_response_size',
        'tts_completed_at', 'status',
    ])

    logger.info(
        f"[process_turn] TTS done | turn={turn_id} "
        f"path={audio_path} exists={out_exists} size={out_size}"
    )

    # ── Update session ─────────────────────────────────────────────────────
    _increment_session_turns(session)

    if needs_transfer:
        _trigger_session_transfer(session, transfer_reason)
        logger.info(f"[process_turn] transfer triggered | session={session.id} reason={transfer_reason}")

    return {
        'status': 'ready',
        'turn_id': turn_id,
        'session_id': str(session.id),
        'audio_path': audio_path,
        'transfer': needs_transfer,
        'transfer_reason': transfer_reason,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fail(turn: ConversationTurn, session: CallSession, reason: str) -> None:
    turn.status = ConversationTurn.Status.FAILED
    turn.error_message = reason
    turn.save(update_fields=['status', 'error_message'])
    logger.error(f"[process_turn] FAILED | turn={turn.id} reason={reason}")


def _increment_session_turns(session: CallSession) -> None:
    """
    Atomically increment total_turns using a database-side F() expression.
    total_turns counts only successfully completed turns (status=READY).
    Failed turns (STT/LLM/TTS failures) are not counted here.
    """
    CallSession.objects.filter(pk=session.pk).update(
        total_turns=F('total_turns') + 1,
    )


def _trigger_session_transfer(session: CallSession, reason: str) -> None:
    CallSession.objects.filter(pk=session.pk).update(
        transfer_triggered=True,
        transfer_reason=reason,
        status=CallSession.Status.TRANSFERRED,
        ended_at=timezone.now(),
    )
