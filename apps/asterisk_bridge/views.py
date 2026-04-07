import json
import logging
import os

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.voice_calls.models import CallRecord, CallSession, ConversationTurn
from tasks.call_tasks import process_call

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _verify_secret(request) -> bool:
    """Verify the shared secret header from Asterisk (skipped if not configured)."""
    secret = getattr(settings, 'ASTERISK_SECRET', '')
    if not secret:
        return True  # no secret configured — allow all (dev / localhost)
    return request.headers.get('X-Asterisk-Secret', '') == secret


# ---------------------------------------------------------------------------
# Legacy single-turn endpoint (preserved for backward compatibility)
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def receive_call(request):
    """
    POST /api/call/
    Accept call metadata from Asterisk and dispatch async processing.

    Body (JSON or form-data):
        caller_number:   str
        audio_file_path: str
    """
    if not _verify_secret(request):
        logger.warning("Unauthorized Asterisk request — bad secret.")
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        if request.content_type == 'application/json':
            data = json.loads(request.body)
        else:
            data = request.POST
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    caller_number = data.get('caller_number', '').strip()
    audio_file_path = data.get('audio_file_path', '').strip()

    if not caller_number or not audio_file_path:
        return JsonResponse(
            {'error': 'caller_number and audio_file_path are required'},
            status=400,
        )

    call = CallRecord.objects.create(
        caller_number=caller_number,
        audio_file_path=audio_file_path,
        status=CallRecord.Status.PENDING,
    )

    process_call.delay(str(call.id))

    logger.info(f"[receive_call] call_id={call.id} caller={caller_number} audio={audio_file_path}")

    return JsonResponse({'call_id': str(call.id), 'status': 'pending'}, status=202)


@require_GET
def call_status(request, call_id: str):
    """
    GET /api/call-status/<call_id>/
    Returns status and response audio path for a legacy CallRecord.
    """
    try:
        call = CallRecord.objects.get(id=call_id)
    except (CallRecord.DoesNotExist, Exception):
        logger.warning(f"call_status: unknown call_id={call_id!r}")
        return JsonResponse({'error': 'Call not found.'}, status=404)

    has_audio = bool(call.response_audio_path)
    logger.info(
        f"[call_status] call={call_id} status={call.status} "
        f"has_audio={has_audio} path={call.response_audio_path or '-'}"
    )

    return JsonResponse({
        'call_id':             str(call.id),
        'status':              call.status,
        'response_audio_path': call.response_audio_path or None,
        'has_audio':           has_audio,
    })


# ---------------------------------------------------------------------------
# Knowledge retrieval test endpoint
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def ask_question(request):
    """
    POST /api/ask/
    Test endpoint for the knowledge retrieval service.
    Restricted to localhost unless DEBUG is on.
    """
    from services.knowledge_retrieval_service import answer_question, FALLBACK_RESPONSE

    if not settings.DEBUG:
        remote_ip = request.META.get('REMOTE_ADDR', '')
        if remote_ip not in ('127.0.0.1', '::1', 'localhost'):
            logger.warning(f"Blocked /api/ask/ from non-local IP: {remote_ip}")
            return JsonResponse({'error': 'Forbidden'}, status=403)

    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'error': 'Request body must be valid JSON.'}, status=400)

    question = data.get('question', '').strip()
    if not question:
        return JsonResponse({'error': '"question" field is required.'}, status=400)

    try:
        answer = answer_question(question)
    except ImproperlyConfigured as exc:
        logger.error(f"/api/ask/ misconfiguration: {exc}")
        return JsonResponse({'error': str(exc)}, status=503)
    except Exception as exc:
        logger.error(f"/api/ask/ OpenAI error: {exc}", exc_info=True)
        return JsonResponse({'error': 'Retrieval failed. Check server logs.'}, status=502)

    return JsonResponse({
        'question': question,
        'answer': answer,
        'source': 'company_documents',
        'found': answer != FALLBACK_RESPONSE,
    })


# ---------------------------------------------------------------------------
# Multi-turn session API
# ---------------------------------------------------------------------------

@csrf_exempt
@require_POST
def session_start(request):
    """
    POST /api/session/start/
    Called by the AGI script at the beginning of a new inbound call.

    Body (JSON):
        caller_number: str

    Returns:
        { "session_id": "<uuid>", "status": "active" }
    """
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    caller_number = data.get('caller_number', 'unknown').strip()

    # Accept language from AGI (set by lang-select dialplan context).
    # Only 'ar' and 'en' are supported; anything else falls back to 'en'.
    lang_raw = data.get('language', 'en').strip().lower()
    language = lang_raw if lang_raw in ('ar', 'en') else 'en'

    session = CallSession.objects.create(
        caller_number=caller_number,
        language=language,
        status=CallSession.Status.ACTIVE,
    )

    logger.info(f"[session_start] session={session.id} caller={caller_number} language={language}")

    return JsonResponse({'session_id': str(session.id), 'status': 'active'}, status=201)


@csrf_exempt
@require_POST
def session_end(request, session_id: str):
    """
    POST /api/session/<session_id>/end/
    Mark a session as completed (or failed) and record end time.

    Body (JSON, all optional):
        status:         'completed' | 'failed' | 'transferred'
        failure_reason: str
    """
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        session = CallSession.objects.get(id=session_id)
    except CallSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found.'}, status=404)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        data = {}

    from django.utils import timezone

    new_status = data.get('status', CallSession.Status.COMPLETED)
    # Validate that the requested status is a known value.
    if new_status not in CallSession.Status.values:
        return JsonResponse(
            {
                'error': f'Invalid status {new_status!r}. '
                         f'Allowed values: {CallSession.Status.values}'
            },
            status=400,
        )
    failure_reason = data.get('failure_reason', '')

    session.status   = new_status
    session.ended_at = timezone.now()
    session.duration_seconds = int(
        (session.ended_at - session.started_at).total_seconds()
    )
    if failure_reason:
        session.failure_reason = failure_reason
    session.save(update_fields=['status', 'ended_at', 'duration_seconds', 'failure_reason'])

    logger.info(f"[session_end] session={session_id} final_status={new_status}")

    return JsonResponse({
        'session_id': str(session.id),
        'status': session.status,
        'total_turns': session.total_turns,
    })


@csrf_exempt
@require_POST
def submit_turn(request, session_id: str):
    """
    POST /api/session/<session_id>/turn/
    Submit a caller audio file for one conversation turn.

    Body (JSON):
        audio_file_path: str   — absolute path to the recorded WAV

    Returns:
        { "turn_id": "<uuid>", "turn_number": N, "status": "pending" }
    """
    if not _verify_secret(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    try:
        session = CallSession.objects.get(id=session_id)
    except CallSession.DoesNotExist:
        return JsonResponse({'error': 'Session not found.'}, status=404)

    if session.status != CallSession.Status.ACTIVE:
        return JsonResponse(
            {'error': f'Session is {session.status}, not active.'},
            status=409,
        )

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    audio_file_path = data.get('audio_file_path', '').strip()
    if not audio_file_path:
        return JsonResponse({'error': 'audio_file_path is required.'}, status=400)

    # Determine next turn number
    last_turn = session.turns.order_by('-turn_number').first()
    turn_number = (last_turn.turn_number + 1) if last_turn else 1

    # Enforce max turns
    max_turns = getattr(settings, 'MAX_CONVERSATION_TURNS', 10)
    if turn_number > max_turns:
        logger.info(f"[submit_turn] max turns reached for session={session_id}")
        return JsonResponse(
            {'error': 'Maximum conversation turns reached.', 'code': 'max_turns'},
            status=422,
        )

    turn = ConversationTurn.objects.create(
        session=session,
        turn_number=turn_number,
        audio_input_path=audio_file_path,
        status=ConversationTurn.Status.PENDING,
    )

    # Dispatch async processing
    from tasks.process_turn import process_turn
    process_turn.delay(str(turn.id))

    logger.info(
        f"[submit_turn] session={session_id} turn={turn.id} "
        f"turn_number={turn_number} audio={audio_file_path}"
    )

    return JsonResponse({
        'turn_id': str(turn.id),
        'turn_number': turn_number,
        'status': 'pending',
    }, status=202)


@require_GET
def turn_status(request, turn_id: str):
    """
    GET /api/turn-status/<turn_id>/
    Poll a ConversationTurn until status == 'ready' or 'failed'.

    Returns:
        {
            "turn_id": ...,
            "status": "ready" | "failed" | "processing" | "pending",
            "audio_response_path": "...",
            "has_audio": true/false,
            "transfer": false,
            "transfer_reason": ""
        }
    """
    try:
        turn = ConversationTurn.objects.get(id=turn_id)
    except ConversationTurn.DoesNotExist:
        logger.warning(f"[turn_status] unknown turn_id={turn_id!r}")
        return JsonResponse({'error': 'Turn not found.'}, status=404)

    # has_audio is true only when the task has confirmed the file exists on disk
    # (audio_response_exists is set by the Celery task after os.path.isfile check)
    has_audio = bool(turn.audio_response_exists and turn.audio_response_path)
    logger.info(
        f"[turn_status] turn={turn_id} status={turn.status} "
        f"has_audio={has_audio} transfer={turn.transfer_needed}"
    )

    return JsonResponse({
        'turn_id':             str(turn.id),
        'status':              turn.status,
        'audio_response_path': turn.audio_response_path or None,
        'has_audio':           has_audio,
        'transfer':            turn.transfer_needed,
        'transfer_reason':     turn.transfer_reason or '',
    })


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@require_GET
def health(request):
    """GET /api/health/ — simple liveness probe."""
    return JsonResponse({'status': 'ok', 'service': 'voice_ai_agent'})
