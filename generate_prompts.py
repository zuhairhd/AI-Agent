#!/usr/bin/env python3
"""
generate_prompts.py — Generate custom Asterisk audio prompts using OpenAI TTS.

Produces 8 kHz / mono / PCM WAV files suitable for Asterisk playback.
Output directory: /var/lib/asterisk/sounds/custom/

Usage (run on the server as root or the asterisk user):
    python3 /home/agent/voice_ai_agent/generate_prompts.py

Requirements:
    pip install openai pydub   (pydub + ffmpeg for format conversion)
    OPENAI_API_KEY must be set in the environment or .env file.

Files produced:
    language_menu.wav       — bilingual DTMF selection prompt
    please_wait_ar.wav      — Arabic wait prompt
    please_wait_en.wav      — English wait prompt
    welcome_future_smart.wav — company welcome message

Each file is converted to 8000 Hz / mono / PCM WAV so Asterisk can play it
without any additional codec configuration.
"""

import os
import sys
import pathlib
import tempfile

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUT_DIR = pathlib.Path('/var/lib/asterisk/sounds/custom')

# Load OPENAI_API_KEY from the project .env if not already in environment
_env_file = pathlib.Path('/home/agent/voice_ai_agent/.env')
if _env_file.exists() and 'OPENAI_API_KEY' not in os.environ:
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            k, _, v = line.partition('=')
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
if not OPENAI_API_KEY:
    sys.exit('ERROR: OPENAI_API_KEY is not set. Export it or ensure .env is populated.')

# TTS settings
TTS_MODEL = 'tts-1'
TTS_VOICE = 'nova'          # clear, professional voice; change if desired

# Prompts to generate  →  (filename_stem, text, voice_override_or_None)
PROMPTS = [
    (
        'language_menu',
        (
            "For English, press 2. "
            "للمتابعة باللغة العربية، اضغط 1. "
            "وللمتابعة باللغة الإنجليزية، اضغط 2."
        ),
        None,
    ),
    (
        'please_wait_ar',
        'لحظة من فضلك، جاري تجهيز الرد.',
        None,
    ),
    (
        'please_wait_en',
        'Please wait while I prepare my response.',
        None,
    ),
    (
        'welcome_future_smart',
        (
            "Hello and welcome to Future Smart Support. "
            "I'm your virtual assistant. "
            "Please note that your call may be recorded for quality and training purposes. "
            "How can I assist you today?"
        ),
        None,
    ),
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _convert_to_asterisk_wav(src_path: str, dst_path: str) -> None:
    """
    Convert any audio file to 8000 Hz / mono / PCM-16 WAV using ffmpeg.
    Raises RuntimeError if ffmpeg is not installed or conversion fails.
    """
    import subprocess
    cmd = [
        'ffmpeg', '-y',
        '-i', src_path,
        '-ar', '8000',
        '-ac', '1',
        '-acodec', 'pcm_s16le',
        dst_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg conversion failed:\n{result.stderr}"
        )


def _generate_prompt(client, stem: str, text: str, voice: str) -> None:
    """Generate one TTS prompt and save it as Asterisk-compatible WAV."""
    dst = OUTPUT_DIR / f'{stem}.wav'
    print(f'  Generating: {dst}')

    # Stream MP3 from OpenAI into a temp file
    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        response = client.audio.speech.create(
            model=TTS_MODEL,
            voice=voice,
            input=text,
            response_format='mp3',
        )
        response.stream_to_file(tmp_path)

        # Convert MP3 → 8 kHz mono PCM WAV
        _convert_to_asterisk_wav(tmp_path, str(dst))
        size = dst.stat().st_size
        print(f'    OK — {size:,} bytes → {dst}')
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit('ERROR: openai package not installed. Run: pip install openai')

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f'Output directory: {OUTPUT_DIR}')

    client = OpenAI(api_key=OPENAI_API_KEY)

    errors = []
    for stem, text, voice_override in PROMPTS:
        voice = voice_override or TTS_VOICE
        try:
            _generate_prompt(client, stem, text, voice)
        except Exception as exc:
            print(f'  ERROR generating {stem}: {exc}')
            errors.append(stem)

    print()
    if errors:
        print(f'DONE with {len(errors)} error(s): {errors}')
        print('Fix the errors and re-run. The successfully generated files are in place.')
        sys.exit(1)
    else:
        print('All prompts generated successfully.')
        print()
        print('Next steps:')
        print('  1. Check that Asterisk can read the files:')
        print('       ls -lh /var/lib/asterisk/sounds/custom/')
        print('  2. Reload dialplan if you edited extensions.conf:')
        print('       asterisk -rx "dialplan reload"')
        print('  3. Test a call.')


if __name__ == '__main__':
    main()
