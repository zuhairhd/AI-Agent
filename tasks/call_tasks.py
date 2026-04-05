import logging
from django.conf import settings
from django.utils import timezone

from celery import shared_task

from apps.voice_calls.models import CallRecord, CallEvent
from services.openai_transcription_service import transcribe
from services.openai_response_service import query_rag

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
    1. Transcribe audio via Whisper
    2. Query RAG via OpenAI Responses API + file_search
    3. Persist results and update status
    """
    logger.info(f"Processing call: {call_id}")

    try:
        call = CallRecord.objects.get(id=call_id)
    except CallRecord.DoesNotExist:
        logger.error(f"CallRecord not found: {call_id}")
        return {'status': 'error', 'reason': 'call_not_found'}

    # Mark as processing
    call.status = CallRecord.Status.PROCESSING
    call.save(update_fields=['status'])
    _log_event(call, CallEvent.EventType.STARTED, {'task_id': self.request.id})

    # Step 1: Transcription
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
        raise  # trigger retry

    # Step 2: RAG query
    try:
        vector_store_id = settings.OPENAI_VECTOR_STORE_ID
        response_text = query_rag(transcript, vector_store_id)
        call.gpt_response_text = response_text
        call.status = CallRecord.Status.ANSWERED
        call.answered_at = timezone.now()
        call.save(update_fields=['gpt_response_text', 'status', 'answered_at'])
        _log_event(call, CallEvent.EventType.ANSWERED, {
            'response_length': len(response_text),
            'response': response_text[:500],
        })
        logger.info(f"[{call_id}] RAG response stored. Status → answered.")
    except Exception as exc:
        logger.error(f"[{call_id}] RAG query failed: {exc}", exc_info=True)
        call.status = CallRecord.Status.FAILED
        call.save(update_fields=['status'])
        _log_event(call, CallEvent.EventType.FAILED, {'stage': 'rag_query', 'error': str(exc)})
        raise  # trigger retry

    return {
        'status': 'answered',
        'call_id': call_id,
        'transcript_length': len(transcript),
        'response_length': len(response_text),
    }
