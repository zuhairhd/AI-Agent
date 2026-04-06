#!/usr/bin/env python3
"""
generate_welcome.py — One-time script to generate the welcome WAV.

Run this ONCE on the server after first deployment (or whenever the welcome
message text changes). The output WAV is Asterisk-compatible (8 kHz / mono /
PCM) and is placed in ASTERISK_SOUNDS_DIR as WELCOME_SOUND_NAME.wav.

Usage:
    cd /home/agent/voice_ai_agent
    source venv/bin/activate
    python asterisk/generate_welcome.py

Environment variables read from .env (via Django settings):
    OPENAI_API_KEY
    ASTERISK_SOUNDS_DIR   default: /var/lib/asterisk/sounds/custom
    WELCOME_SOUND_NAME    default: welcome_future_smart
    COMPANY_NAME          default: Future Smart Support
"""
import audioop
import os
import sys
import wave

# ---------------------------------------------------------------------------
# Bootstrap Django settings so we can read env variables cleanly
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.base')

import django
django.setup()

from django.conf import settings
from openai import OpenAI

# ---------------------------------------------------------------------------
# Welcome message (exact text required by project brief)
# ---------------------------------------------------------------------------
WELCOME_TEXT = (
    "Hello and welcome to Future Smart Support. "
    "I'm your virtual assistant. "
    "Please note that your call may be recorded for quality and training purposes. "
    "How can I assist you today?"
)

# ---------------------------------------------------------------------------
# Audio constants (Asterisk-compatible)
# ---------------------------------------------------------------------------
TARGET_RATE   = 8_000
TARGET_CH     = 1
TARGET_WIDTH  = 2       # 16-bit signed PCM


def main():
    sounds_dir  = getattr(settings, 'ASTERISK_SOUNDS_DIR', '/var/lib/asterisk/sounds/custom')
    sound_name  = getattr(settings, 'WELCOME_SOUND_NAME', 'welcome_future_smart')
    company     = getattr(settings, 'COMPANY_NAME', 'Future Smart Support')
    api_key     = getattr(settings, 'OPENAI_API_KEY', '')

    if not api_key:
        print("ERROR: OPENAI_API_KEY is not set.", file=sys.stderr)
        sys.exit(1)

    os.makedirs(sounds_dir, exist_ok=True)
    dest_path = os.path.join(sounds_dir, f"{sound_name}.wav")

    print(f"Generating welcome audio for: {company}")
    print(f"Text: {WELCOME_TEXT}")
    print(f"Output: {dest_path}")

    client = OpenAI(api_key=api_key)

    # Request raw PCM at 24 kHz (OpenAI default for 'pcm' format)
    response = client.audio.speech.create(
        model='tts-1',
        voice='alloy',
        input=WELCOME_TEXT,
        response_format='pcm',  # raw signed 16-bit PCM at 24 000 Hz mono
    )

    raw_pcm = response.content

    # Resample 24 000 Hz → 8 000 Hz
    pcm_8k, _ = audioop.ratecv(
        raw_pcm,
        TARGET_WIDTH,
        TARGET_CH,
        24_000,
        TARGET_RATE,
        None,
    )

    # Write WAV
    with wave.open(dest_path, 'wb') as wf:
        wf.setnchannels(TARGET_CH)
        wf.setsampwidth(TARGET_WIDTH)
        wf.setframerate(TARGET_RATE)
        wf.writeframes(pcm_8k)

    size = os.path.getsize(dest_path)
    print(f"Done. File size: {size} bytes")
    print(f"Asterisk can now play: custom/{sound_name}")


if __name__ == '__main__':
    main()
