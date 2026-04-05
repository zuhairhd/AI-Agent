import logging
import json

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from apps.voice_calls.models import CallRecord
from tasks.call_tasks import process_call

logger = logging.getLogger(__name__)


def _verify_secret(request) -> bool:
    """Verify the shared secret header from Asterisk."""
    secret = settings.ASTERISK_SECRET
    if not secret:
        return True  # no secret configured — allow all (dev mode)
    return request.headers.get('X-Asterisk-Secret', '') == secret


@csrf_exempt
@require_POST
def receive_call(request):
    """
    POST /api/call/
    Accept call metadata from Asterisk and dispatch async processing.

    Body (JSON or form-data):
        caller_number: str
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

    logger.info(f"Call received: {call.id} from {caller_number}, audio={audio_file_path}")

    return JsonResponse(
        {'call_id': str(call.id), 'status': 'pending'},
        status=202,
    )


@csrf_exempt
@require_POST
def ask_question(request):
    """
    POST /api/ask/
    Test endpoint for the knowledge retrieval service.

    Body (JSON):
        question: str   — the question to answer from company documents

    Returns JSON:
        { "question": "...", "answer": "..." }

    Restricted to DEBUG mode or requests from localhost / 127.0.0.1.
    For production, add ASTERISK_SECRET header auth or restrict via nginx.
    """
    from services.knowledge_retrieval_service import answer_question, FALLBACK_RESPONSE

    # Restrict to local access unless DEBUG is on
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
        return JsonResponse(
            {'error': 'Retrieval failed. Check server logs.'},
            status=502,
        )

    return JsonResponse({
        'question': question,
        'answer': answer,
        'source': 'company_documents',
        'found': answer != FALLBACK_RESPONSE,
    })
