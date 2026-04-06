import logging
import os
from openai import OpenAI
from django.conf import settings

logger = logging.getLogger(__name__)


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def transcribe(audio_file_path: str) -> str:
    """
    Transcribe a WAV audio file using OpenAI Whisper.
    Returns the transcribed text string.
    """
    client = _get_client()

    if not os.path.exists(audio_file_path):
        raise FileNotFoundError(f"Audio file not found: {audio_file_path}")

    logger.info(f"Transcribing audio: {audio_file_path}")

    with open(audio_file_path, 'rb') as audio_file:
        response = client.audio.transcriptions.create(
            model='whisper-1',
            file=audio_file,
            response_format='text',
        )

    transcript = response.strip() if isinstance(response, str) else response.text.strip()
    logger.info(f"Transcription complete ({len(transcript)} chars)")
    return transcript
