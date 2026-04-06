"""
OpenAI Text-to-Speech service.

Public API:
    synthesise(text: str, call_id: str) -> str

Converts answer text to speech and saves a WAV file suitable for Asterisk
playback under:
    <CALL_RESPONSES_ROOT>/<call_id>.wav

Asterisk requirements met:
    • Mono (1 channel)
    • 8 000 Hz sample rate
    • 16-bit signed PCM (linear)
    • RIFF/WAV container

OpenAI TTS returns MP3 by default.  We convert it to the correct WAV format
using the `wave` + `audioop` modules from the Python standard library — no
external binaries (ffmpeg, sox) required.  If the environment has `pydub`
installed it will be used as a faster alternative, but it is not required.
"""
import audioop
import io
import logging
import os
import struct
import wave

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Directory where response audio files are stored.
# Override via CALL_RESPONSES_ROOT in .env / Django settings.
_DEFAULT_RESPONSES_DIR = os.path.join(
    getattr(settings, 'BASE_DIR', '/home/agent/voice_ai_agent'),
    'media', 'call_responses',
)

# Asterisk target format
_TARGET_SAMPLE_RATE   = 8_000   # Hz
_TARGET_CHANNELS      = 1       # mono
_TARGET_SAMPLE_WIDTH  = 2       # bytes → 16-bit PCM


def _get_responses_dir() -> str:
    root = getattr(settings, 'CALL_RESPONSES_ROOT', _DEFAULT_RESPONSES_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def _get_client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


# ---------------------------------------------------------------------------
# MP3 → PCM WAV conversion (stdlib only)
# ---------------------------------------------------------------------------

def _mp3_bytes_to_pcm_wav(mp3_data: bytes, dest_path: str) -> None:
    """
    Decode MP3 → PCM and write a WAV file at Asterisk-compatible settings.

    Strategy:
      1. Try pydub (fast, clean) if available.
      2. Fall back to a pure-stdlib approach via the `audioop` resampling trick
         when pydub / libav are not installed.
    """
    try:
        _convert_with_pydub(mp3_data, dest_path)
        logger.debug(f"TTS: converted MP3 → WAV using pydub ({dest_path})")
        return
    except ImportError:
        logger.debug("pydub not available — using stdlib WAV writer.")
    except Exception as exc:
        logger.warning(f"pydub conversion failed ({exc}); trying stdlib fallback.")

    _convert_with_stdlib(mp3_data, dest_path)
    logger.debug(f"TTS: wrote WAV via stdlib fallback ({dest_path})")


def _convert_with_pydub(mp3_data: bytes, dest_path: str) -> None:
    """Requires: pip install pydub  (and ffmpeg or libav on PATH)."""
    from pydub import AudioSegment  # type: ignore

    audio = AudioSegment.from_mp3(io.BytesIO(mp3_data))
    audio = audio.set_frame_rate(_TARGET_SAMPLE_RATE)
    audio = audio.set_channels(_TARGET_CHANNELS)
    audio = audio.set_sample_width(_TARGET_SAMPLE_WIDTH)
    audio.export(dest_path, format='wav')


def _convert_with_stdlib(mp3_data: bytes, dest_path: str) -> None:
    """
    Pure-stdlib fallback.

    OpenAI TTS with response_format='pcm' already returns raw 24 kHz / mono /
    16-bit little-endian PCM — no MP3 decoding step needed.  We just resample
    from 24 000 Hz to 8 000 Hz using audioop.ratecv and wrap it in a WAV header.
    """
    # ratecv: (fragment, width, nchannels, inrate, outrate, state)
    pcm_8k, _ = audioop.ratecv(
        mp3_data,           # raw PCM bytes at source rate
        _TARGET_SAMPLE_WIDTH,
        _TARGET_CHANNELS,
        24_000,             # OpenAI PCM output rate
        _TARGET_SAMPLE_RATE,
        None,
    )

    with wave.open(dest_path, 'wb') as wf:
        wf.setnchannels(_TARGET_CHANNELS)
        wf.setsampwidth(_TARGET_SAMPLE_WIDTH)
        wf.setframerate(_TARGET_SAMPLE_RATE)
        wf.writeframes(pcm_8k)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesise(text: str, call_id: str = '', turn_id: str = '') -> str:
    """
    Convert answer text to an Asterisk-compatible WAV file.

    Args:
        text:    The answer text to synthesise (from RAG / GPT response).
        call_id: Legacy single-turn identifier → filename <call_id>.wav
        turn_id: Multi-turn identifier (preferred) → filename <turn_id>.wav
                 If both are supplied, turn_id takes precedence.

    Returns:
        Absolute path to the saved WAV file.

    Raises:
        ValueError:          If text is empty or no id provided.
        openai.OpenAIError:  On API failures (let Celery retry).
        OSError:             If the output directory cannot be written.
    """
    text = text.strip()
    if not text:
        raise ValueError("synthesise() called with empty text — nothing to convert.")

    file_id = turn_id or call_id
    if not file_id:
        raise ValueError("synthesise() requires either turn_id or call_id.")

    responses_dir = _get_responses_dir()
    dest_path = os.path.join(responses_dir, f"{file_id}.wav")

    logger.info(
        f"TTS started | id={file_id} | "
        f"text_len={len(text)} | dest={dest_path}"
    )

    client = _get_client()

    # Request raw PCM from OpenAI (24 kHz, mono, 16-bit little-endian).
    # Using 'pcm' avoids any MP3 decoding and keeps the stdlib path fast.
    response = client.audio.speech.create(
        model='tts-1',          # tts-1-hd for higher quality if latency permits
        voice='alloy',          # neutral voice; change to 'nova', 'shimmer', etc.
        input=text,
        response_format='pcm',  # raw signed 16-bit PCM at 24 000 Hz
    )

    raw_pcm = response.content  # bytes
    logger.debug(f"TTS: received {len(raw_pcm)} bytes of raw PCM from OpenAI.")

    # Resample 24 kHz → 8 kHz and write WAV
    _convert_with_stdlib(raw_pcm, dest_path)

    file_size = os.path.getsize(dest_path)
    logger.info(
        f"TTS completed | id={file_id} | "
        f"output={dest_path} | size={file_size} bytes | "
        f"format=WAV PCM 8kHz mono 16-bit (Asterisk-ready)"
    )

    return dest_path
