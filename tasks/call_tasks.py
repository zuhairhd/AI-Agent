import logging
from django.conf import settings
from django.utils import timezone

from celery import shared_task

from apps.voice_calls.models import CallRecord, CallEvent
from services.openai_transcription_service import transcribe
from services.openai_response_service import query_rag
from services.openai_tts_service import synthesise

logger = logging.getLogger(__name__)


def _log_event(call: CallRecord, event_type: str, payload: dict = None) -> None:
    CallEvent.objects.create(
        call=call,
        event_type=event_type,
        payload=payload or {},
    )


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60,
    name='tasks.process_call',
)
def process_call(self, call_id: str) -> dict:
    """
    Full call processing pipeline:
      1. Transcribe caller audio via Whisper
      2. Query RAG (OpenAI Responses API + file_search)
      3. Convert answer text to speech (TTS → WAV)
      4. Persist all results; final status → audio_ready
    """
    logger.info(f"Processing call: {call_id}")

    try:
        call = CallRecord.objects.get(id=call_id)
    except CallRecord.DoesNotExist:
        logger.error(f"CallRecord not found: {call_id}")
        return {'status': 'error', 'reason': 'call_not_found'}

    # ── Mark as processing ──────────────────────────────────────────────────
    call.status = CallRecord.Status.PROCESSING
    call.save(update_fields=['status'])
    _log_event(call, CallEvent.EventType.STARTED, {'task_id': self.request.id})

    # ── Step 1: Transcription ───────────────────────────────────────────────
    try:
        transcript = transcribe(call.audio_file_path)
        call.transcript_text = transcript
        call.save(update_fields=['transcript_text'])
        _log_event(call, CallEvent.EventType.TRANSCRIBED, {
            'transcript_length': len(transcript),
            'preview': transcript[:200],
        })
        logger.info(f"[{call_id}] Transcription complete.")
    except Exception as exc:
        logger.error(f"[{call_id}] Transcription failed: {exc}", exc_info=True)
        call.status = CallRecord.Status.FAILED
        call.save(update_fields=['status'])
        _log_event(call, CallEvent.EventType.FAILED, {'stage': 'transcription', 'error': str(exc)})
        raise  # trigger Celery autoretry

    # ── Step 2: RAG query ───────────────────────────────────────────────────
    try:
        vector_store_id = settings.OPENAI_VECTOR_STORE_ID
        response_text = query_rag(transcript, vector_store_id)
        call.gpt_response_text = response_text
        call.answered_at = timezone.now()
        # Keep status as 'processing' — TTS step sets the final status
        call.save(update_fields=['gpt_response_text', 'answered_at'])
        _log_event(call, CallEvent.EventType.ANSWERED, {
            'response_length': len(response_text),
            'response': response_text[:500],
        })
        logger.info(f"[{call_id}] RAG response stored.")
    except Exception as exc:
        logger.error(f"[{call_id}] RAG query failed: {exc}", exc_info=True)
        call.status = CallRecord.Status.FAILED
        call.save(update_fields=['status'])
        _log_event(call, CallEvent.EventType.FAILED, {'stage': 'rag_query', 'error': str(exc)})
        raise  # trigger Celery autoretry

    # ── Step 3: TTS — convert answer to Asterisk-compatible WAV ────────────
    try:
        audio_path = synthesise(text=response_text, call_id=str(call_id))
        call.response_audio_path = audio_path
        call.status = CallRecord.Status.AUDIO_READY
        call.save(update_fields=['response_audio_path', 'status'])
        _log_event(call, CallEvent.EventType.TTS_DONE, {
            'audio_path': audio_path,
            'response_length': len(response_text),
        })
        logger.info(f"[{call_id}] TTS complete. Audio ready at: {audio_path}")
    except Exception as exc:
        # TTS failure is non-fatal for the RAG result:
        # mark as 'answered' (text still usable) rather than 'failed',
        # but log clearly so operators know audio is missing.
        logger.error(f"[{call_id}] TTS failed: {exc}", exc_info=True)
        call.status = CallRecord.Status.ANSWERED
        call.save(update_fields=['status'])
        _log_event(call, CallEvent.EventType.FAILED, {
            'stage': 'tts',
            'error': str(exc),
            'note': 'RAG answer saved; audio not generated.',
        })
        # Do NOT re-raise — the text answer is valid; TTS is best-effort.
        return {
            'status': 'answered',
            'call_id': call_id,
            'tts': 'failed',
            'transcript_length': len(transcript),
            'response_length': len(response_text),
        }

    return {
        'status': 'audio_ready',
        'call_id': call_id,
        'audio_path': audio_path,
        'transcript_length': len(transcript),
        'response_length': len(response_text),
    }
