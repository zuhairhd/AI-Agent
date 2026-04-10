"""
OpenAI TTS service.

Goals
-----
- Generate phone-friendly Arabic/English TTS
- Keep Arabic pronunciation cleaner by normalizing text first
- Split long replies into smaller chunks to avoid awkward long synthesis
- Output Asterisk-ready WAV PCM 8kHz mono 16-bit
- Keep the public API simple:

    synthesise(text: str, turn_id: str) -> str

Config (optional)
-----------------
You may define any of these in Django settings or .env:

OPENAI_TTS_MODEL=gpt-4o-mini-tts
OPENAI_TTS_VOICE=alloy
OPENAI_TTS_VOICE_AR=alloy
OPENAI_TTS_VOICE_EN=alloy
OPENAI_TTS_MAX_CHARS_AR=140
OPENAI_TTS_MAX_CHARS_EN=180
OPENAI_TTS_SPEED=1.0
MEDIA_ROOT=/path/to/media

This service writes final files to:
    <MEDIA_ROOT>/call_responses/<turn_id>.wav
"""

from __future__ import annotations

import io
import logging
import os
import re
import wave
from pathlib import Path
from typing import List

from django.conf import settings
from openai import OpenAI

logger = logging.getLogger(__name__)

# Asterisk-friendly output
OUTPUT_SAMPLE_RATE = 8000
OUTPUT_CHANNELS = 1
OUTPUT_SAMPLE_WIDTH = 2  # 16-bit PCM

# OpenAI PCM is raw mono 24kHz 16-bit little-endian in common usage patterns.
# We downsample it to 8kHz ourselves.
OPENAI_PCM_INPUT_RATE = 24000

DEFAULT_MODEL = "gpt-4o-mini-tts"
DEFAULT_VOICE = "alloy"
DEFAULT_SPEED = 1.0

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
MULTISPACE_RE = re.compile(r"\s+")
LATIN_WORD_RE = re.compile(r"[A-Za-z]+")


# ---------------------------------------------------------------------------
# Basic helpers
# ---------------------------------------------------------------------------

def _client() -> OpenAI:
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _get_setting(name: str, default):
    return getattr(settings, name, default)


def _ensure_output_dir() -> Path:
    media_root = Path(_get_setting("MEDIA_ROOT", "media"))
    out_dir = media_root / "call_responses"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _detect_language(text: str) -> str:
    return "ar" if ARABIC_RE.search(text or "") else "en"


def _choose_model() -> str:
    return _get_setting("OPENAI_TTS_MODEL", DEFAULT_MODEL)


def _choose_voice(language: str) -> str:
    if language == "ar":
        return _get_setting("OPENAI_TTS_VOICE_AR", _get_setting("OPENAI_TTS_VOICE", DEFAULT_VOICE))
    return _get_setting("OPENAI_TTS_VOICE_EN", _get_setting("OPENAI_TTS_VOICE", DEFAULT_VOICE))


def _choose_speed() -> float:
    try:
        value = float(_get_setting("OPENAI_TTS_SPEED", DEFAULT_SPEED))
    except Exception:
        value = DEFAULT_SPEED
    return max(0.75, min(1.25, value))


# ---------------------------------------------------------------------------
# Text normalization
# ---------------------------------------------------------------------------

def _normalize_common(text: str) -> str:
    text = (text or "").strip()

    # Remove markdown-ish artifacts
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^[\-\*\d\.\)\s]+", "", text, flags=re.M)

    # Normalize whitespace
    text = text.replace("\n", " ")
    text = MULTISPACE_RE.sub(" ", text).strip()

    return text


def _normalize_arabic(text: str) -> str:
    text = _normalize_common(text)

    # Make spoken Arabic more natural for TTS
    replacements = {
        "VoiceGate AI": "فويس جيت إي آي",
        "AI": "إي آي",
        "24/7": "أربع وعشرين ساعة طوال أيام الأسبوع",
        "&": " و ",
        "/": " أو ",
        "،،": "،",
        "..": ".",
        "؟؟": "؟",
    }

    for src, dst in replacements.items():
        text = text.replace(src, dst)

    # Normalize punctuation spacing
    text = re.sub(r"\s*،\s*", "، ", text)
    text = re.sub(r"\s*\.\s*", ". ", text)
    text = re.sub(r"\s*؟\s*", "؟ ", text)
    text = MULTISPACE_RE.sub(" ", text).strip()

    return text


def _normalize_english(text: str) -> str:
    text = _normalize_common(text)

    replacements = {
        "&": " and ",
        "/": " or ",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)

    text = MULTISPACE_RE.sub(" ", text).strip()
    return text


def _prepare_text(text: str, language: str) -> str:
    text = _normalize_arabic(text) if language == "ar" else _normalize_english(text)

    # Trim overlong phone text a bit before chunking
    max_len = 260 if language == "ar" else 320
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0].strip()

    return text


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _split_sentences(text: str, language: str) -> List[str]:
    """
    Split on spoken punctuation, preserving natural phone rhythm.
    """
    if not text:
        return []

    if language == "ar":
        parts = re.split(r"(?<=[\.\!\؟،])\s+", text)
    else:
        parts = re.split(r"(?<=[\.\!\?\,])\s+", text)

    return [p.strip() for p in parts if p.strip()]


def _chunk_text(text: str, language: str) -> List[str]:
    """
    Create short TTS chunks.
    Arabic stays shorter to improve clarity.
    """
    max_chars = int(_get_setting("OPENAI_TTS_MAX_CHARS_AR", 140) if language == "ar"
                    else _get_setting("OPENAI_TTS_MAX_CHARS_EN", 180))

    sentences = _split_sentences(text, language)
    if not sentences:
        return [text] if text else []

    chunks: List[str] = []
    current = ""

    for sentence in sentences:
        candidate = sentence if not current else f"{current} {sentence}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            if len(sentence) <= max_chars:
                current = sentence
            else:
                # hard split long sentence
                remaining = sentence
                while len(remaining) > max_chars:
                    cut = remaining[:max_chars]
                    if " " in cut:
                        cut = cut.rsplit(" ", 1)[0]
                    chunks.append(cut.strip())
                    remaining = remaining[len(cut):].strip()
                current = remaining

    if current:
        chunks.append(current.strip())

    return chunks


# ---------------------------------------------------------------------------
# Audio conversion
# ---------------------------------------------------------------------------

def _downsample_pcm_24k_to_8k(raw_pcm: bytes) -> bytes:
    """
    Very simple 24kHz -> 8kHz downsampling by taking every third sample.
    Input/output are 16-bit little-endian mono PCM.

    This is intentionally simple and dependency-free.
    """
    if not raw_pcm:
        return b""

    # 16-bit mono => 2 bytes per sample
    sample_width = 2
    frame_count = len(raw_pcm) // sample_width

    # every 3rd sample for 24k -> 8k
    out = bytearray()
    step = 3
    for i in range(0, frame_count, step):
        start = i * sample_width
        out.extend(raw_pcm[start:start + sample_width])

    return bytes(out)


def _write_wav(path: Path, pcm_8k: bytes) -> None:
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(OUTPUT_CHANNELS)
        wf.setsampwidth(OUTPUT_SAMPLE_WIDTH)
        wf.setframerate(OUTPUT_SAMPLE_RATE)
        wf.writeframes(pcm_8k)


# ---------------------------------------------------------------------------
# OpenAI speech call
# ---------------------------------------------------------------------------

def _speech_create_pcm(client: OpenAI, *, model: str, voice: str, text: str, speed: float) -> bytes:
    """
    Request raw PCM from OpenAI.

    The API docs list supported output formats including wav and pcm.
    We request pcm so we can produce a deterministic Asterisk-ready 8kHz wav. :contentReference[oaicite:1]{index=1}
    """
    kwargs = {
        "model": model,
        "voice": voice,
        "input": text,
        "speed": speed,
        "format": "pcm",
    }

    try:
        response = client.audio.speech.create(**kwargs)
    except TypeError:
        # Compatibility fallback for SDK variants that still use response_format
        kwargs.pop("format", None)
        kwargs["response_format"] = "pcm"
        response = client.audio.speech.create(**kwargs)

    # SDK response may expose content/read/iter_bytes depending on version
    if hasattr(response, "read") and callable(response.read):
        data = response.read()
        if data:
            return data

    if hasattr(response, "content"):
        data = response.content
        if data:
            return data

    if hasattr(response, "iter_bytes") and callable(response.iter_bytes):
        return b"".join(response.iter_bytes())

    raise RuntimeError("TTS response did not expose readable audio bytes.")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def synthesise(text: str, turn_id: str) -> str:
    """
    Generate Asterisk-ready WAV for one call turn.

    Returns absolute file path.
    """
    if not text or not str(text).strip():
        raise ValueError("TTS text is empty.")

    if not turn_id:
        raise ValueError("turn_id is required.")

    language = _detect_language(text)
    model = _choose_model()
    voice = _choose_voice(language)
    speed = _choose_speed()

    prepared = _prepare_text(text, language)
    chunks = _chunk_text(prepared, language)

    if not chunks:
        raise ValueError("No TTS chunks generated after normalization.")

    out_dir = _ensure_output_dir()
    dest = out_dir / f"{turn_id}.wav"

    logger.info(
        "TTS started | id=%s | lang=%s | model=%s | voice=%s | chunks=%s | text_len=%s | dest=%s",
        turn_id,
        language,
        model,
        voice,
        len(chunks),
        len(prepared),
        dest,
    )

    client = _client()
    combined_pcm_8k = bytearray()
    total_raw_bytes = 0

    for idx, chunk in enumerate(chunks, start=1):
        logger.debug("TTS chunk %s/%s | id=%s | len=%s | text=%r", idx, len(chunks), turn_id, len(chunk), chunk)

        raw_pcm_24k = _speech_create_pcm(
            client,
            model=model,
            voice=voice,
            text=chunk,
            speed=speed,
        )
        total_raw_bytes += len(raw_pcm_24k)

        pcm_8k = _downsample_pcm_24k_to_8k(raw_pcm_24k)
        combined_pcm_8k.extend(pcm_8k)

        # Tiny silence between chunks so concatenation sounds less abrupt
        silence_ms = 90 if language == "ar" else 70
        silence_samples = int(OUTPUT_SAMPLE_RATE * (silence_ms / 1000.0))
        combined_pcm_8k.extend(b"\x00\x00" * silence_samples)

    _write_wav(dest, bytes(combined_pcm_8k))

    out_exists = dest.is_file()
    out_size = dest.stat().st_size if out_exists else None

    logger.debug(
        "TTS: received %s bytes of raw PCM from OpenAI across %s chunk(s).",
        total_raw_bytes,
        len(chunks),
    )
    logger.info(
        "TTS completed | id=%s | output=%s | size=%s bytes | format=WAV PCM 8kHz mono 16-bit (Asterisk-ready)",
        turn_id,
        dest,
        out_size,
    )

    return str(dest)
