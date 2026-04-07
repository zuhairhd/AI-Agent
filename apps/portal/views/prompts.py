"""
Call prompt management views.
GET/PUT text, trigger audio regeneration via TTS, upload custom audio.
"""
import logging
import os

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from apps.portal.models import CallPrompt
from apps.portal.serializers import CallPromptSerializer

logger = logging.getLogger(__name__)

# Default prompts seeded on first access
DEFAULT_PROMPTS = [
    {'stem': 'language_menu',    'language': 'bilingual', 'text': 'For English press 2. للمتابعة باللغة العربية اضغط 1.'},
    {'stem': 'please_wait_ar',   'language': 'ar',        'text': 'لحظة من فضلك.'},
    {'stem': 'please_wait_en',   'language': 'en',        'text': 'Just a moment, please.'},
    {'stem': 'please_ask_ar',    'language': 'ar',        'text': 'يرجى توضيح مشكلتك الآن.'},
    {'stem': 'please_ask_en',    'language': 'en',        'text': 'Please tell me your issue now.'},
    {'stem': 'farewell_ar',      'language': 'ar',        'text': 'شكراً لاتصالك. مع السلامة.'},
    {'stem': 'farewell_en',      'language': 'en',        'text': 'Thank you for calling. Goodbye!'},
]


def _ensure_defaults():
    for d in DEFAULT_PROMPTS:
        CallPrompt.objects.get_or_create(stem=d['stem'], defaults=d)


@api_view(['GET'])
def prompts_list_view(request):
    _ensure_defaults()
    prompts = CallPrompt.objects.order_by('stem')
    return Response(CallPromptSerializer(prompts, many=True).data)


@api_view(['GET', 'PUT'])
def prompt_detail_view(request, stem):
    _ensure_defaults()
    try:
        prompt = CallPrompt.objects.get(stem=stem)
    except CallPrompt.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CallPromptSerializer(prompt).data)

    # PUT — update text and/or enabled
    allowed = ('text', 'enabled', 'language')
    for k, v in request.data.items():
        if k in allowed:
            setattr(prompt, k, v)
    prompt.save()
    return Response(CallPromptSerializer(prompt).data)


@api_view(['POST'])
def prompt_regenerate_view(request, stem):
    """
    POST /api/portal/prompts/<stem>/regenerate/
    Re-generate the audio file from the stored text using OpenAI TTS.
    """
    try:
        prompt = CallPrompt.objects.get(stem=stem)
    except CallPrompt.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    sounds_dir = getattr(settings, 'ASTERISK_SOUNDS_DIR', '/var/lib/asterisk/sounds/custom')
    os.makedirs(sounds_dir, exist_ok=True)

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        voice  = 'alloy'
        wav_path = os.path.join(sounds_dir, f"{stem}.wav")

        response = client.audio.speech.create(
            model='tts-1',
            voice=voice,
            input=prompt.text,
        )
        response.stream_to_file(wav_path)

        # Convert to Asterisk-friendly format via ffmpeg if available
        try:
            import subprocess
            out_8k = os.path.join(sounds_dir, f"{stem}_8k.wav")
            subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path,
                 '-ar', '8000', '-ac', '1', '-f', 'wav', out_8k],
                check=True, capture_output=True,
            )
            os.replace(out_8k, wav_path)
        except Exception as fe:
            logger.warning(f"[prompts] ffmpeg conversion skipped: {fe}")

        prompt.audio_path   = wav_path
        prompt.audio_exists = os.path.isfile(wav_path)
        prompt.version     += 1
        prompt.save(update_fields=['audio_path', 'audio_exists', 'version'])

        logger.info(f"[prompts] Regenerated audio for {stem}")
        return Response(CallPromptSerializer(prompt).data)

    except Exception as exc:
        logger.error(f"[prompts] Regeneration failed for {stem}: {exc}", exc_info=True)
        return Response({'detail': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def prompt_upload_audio_view(request, stem):
    """
    POST /api/portal/prompts/<stem>/upload-audio/
    Upload a custom WAV file for this prompt (replaces generated audio).
    """
    try:
        prompt = CallPrompt.objects.get(stem=stem)
    except CallPrompt.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    audio_file = request.FILES.get('audio')
    if not audio_file:
        return Response({'detail': 'No audio file provided.'}, status=status.HTTP_400_BAD_REQUEST)

    sounds_dir = getattr(settings, 'ASTERISK_SOUNDS_DIR', '/var/lib/asterisk/sounds/custom')
    os.makedirs(sounds_dir, exist_ok=True)

    dest = os.path.join(sounds_dir, f"{stem}.wav")
    with open(dest, 'wb') as f:
        for chunk in audio_file.chunks():
            f.write(chunk)

    # Convert to 8kHz mono
    try:
        import subprocess
        tmp = dest + '.tmp.wav'
        subprocess.run(
            ['ffmpeg', '-y', '-i', dest, '-ar', '8000', '-ac', '1', '-f', 'wav', tmp],
            check=True, capture_output=True,
        )
        os.replace(tmp, dest)
    except Exception as fe:
        logger.warning(f"[prompts] ffmpeg conversion skipped on upload: {fe}")

    prompt.audio_path   = dest
    prompt.audio_exists = True
    prompt.version     += 1
    prompt.save(update_fields=['audio_path', 'audio_exists', 'version'])

    logger.info(f"[prompts] Custom audio uploaded for {stem}")
    return Response(CallPromptSerializer(prompt).data)
