#!/usr/bin/env python3
"""
generate_prompts.py — Flexible Asterisk prompt generation tool.

Generates telephony-native audio files (.wav, .ulaw, .alaw) from text via
OpenAI TTS.  Prompt text is managed dynamically — the tool resolves which
prompts to build from the first available source in this priority order:

  1. --input-file  (explicit JSON or stem|text file passed on the command line)
  2. prompts.json  (the default editable source, auto-discovered next to this
                    script; edit this file to change text without code changes)
  3. Interactive   (operator types stem|text pairs when stdin is a TTY and no
                    JSON source was found)
  4. Built-in defaults (hardcoded fallback; always available; backward-compatible)

Hash-based caching (SHA-256 over text + voice + model + sample_rate + channels)
prevents redundant TTS calls.  Only prompts whose text or settings have changed
since the last run are regenerated.  Use --force to bypass the cache entirely.

The cache file (prompt_cache.json) is stored inside --output-dir alongside the
audio files.  The default output directory (/var/lib/asterisk/sounds/custom/)
is outside the repository, so no .gitignore entry is required.  If you run with
--output-dir pointing at a path inside the repo (e.g. during local development),
add prompt_cache.json to your .gitignore manually.

Usage examples
--------------
# Generate all prompts (auto-discovers prompts.json, or falls back to built-ins)
python generate_prompts.py

# Edit only the text in prompts.json, then regenerate only changed prompts
python generate_prompts.py

# Use a custom input file (JSON or stem|text)
python generate_prompts.py --input-file /path/to/custom.json

# Regenerate a single prompt regardless of cache
python generate_prompts.py --only please_ask_ar --force

# Force-regenerate everything
python generate_prompts.py --force

# Custom output directory, voice, and formats
python generate_prompts.py --output-dir /tmp/test --voice alloy --format-set wav,ulaw

# Apply file ownership after generation (optional; non-fatal if it fails)
python generate_prompts.py --owner asterisk:asterisk
"""

import argparse
import hashlib
import json
import os
import pathlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_DIR  = '/var/lib/asterisk/sounds/custom'
DEFAULT_SAMPLE_RATE = 8000
DEFAULT_CHANNELS    = 1          # 1 = mono (telephony standard)
DEFAULT_VOICE       = 'nova'
DEFAULT_MODEL       = 'tts-1'
DEFAULT_FORMATS     = ['wav', 'ulaw', 'alaw']

# Auto-discovered .env file (same directory as this script)
_ENV_FILE = pathlib.Path(__file__).parent / '.env'

# Cache file is stored inside output_dir alongside the audio files.
CACHE_FILENAME = 'prompt_cache.json'

# ---------------------------------------------------------------------------
# Built-in prompt defaults
# Backward-compatible fallback used when no external source is available.
# These match the voice_agent.agi expectations exactly.
# ---------------------------------------------------------------------------

BUILTIN_DEFAULTS: list[dict] = [
    {
        'stem': 'language_menu',
        'text': (
            'For English, press 2. '
            'للمتابعة باللغة العربية، اضغط 1. '
            'وللمتابعة باللغة الإنجليزية، اضغط 2.'
        ),
    },
    {
        'stem': 'please_ask_ar',
        'text': 'يرجى توضيح مشكلتك الآن.',
    },
    {
        'stem': 'please_ask_en',
        'text': 'Please tell me your issue now.',
    },
    {
        'stem': 'please_wait_ar',
        'text': 'لحظة من فضلك.',
    },
    {
        'stem': 'please_wait_en',
        'text': 'Just a moment, please.',
    },
]


# ---------------------------------------------------------------------------
# .env loader  (no python-dotenv required)
# ---------------------------------------------------------------------------

def _load_dotenv() -> None:
    """Load KEY=VALUE pairs from the project .env into os.environ (non-override)."""
    if not _ENV_FILE.exists():
        return
    for raw in _ENV_FILE.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, _, val = line.partition('=')
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


# ---------------------------------------------------------------------------
# Prompt source resolution
# ---------------------------------------------------------------------------

def _load_json_source(path: pathlib.Path) -> list[dict]:
    """
    Load prompts from a JSON file.  Accepts two shapes:

      a) Full schema:  {"version": 1, "defaults": {...}, "prompts": [...]}
      b) Bare list:    [{"stem": ..., "text": ...}, ...]

    Only "stem" and "text" are required on each entry.  Optional fields:
      "language", "version", "enabled", "voice", "model"

    Entries with enabled=false are silently skipped.
    """
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (json.JSONDecodeError, OSError) as exc:
        sys.exit(f'ERROR: Could not parse {path}: {exc}')

    if isinstance(raw, list):
        entries       = raw
        file_defaults = {}
    else:
        entries       = raw.get('prompts', [])
        file_defaults = raw.get('defaults', {}) or {}

    result: list[dict] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        # Only stem + text are required; everything else is optional.
        stem = (entry.get('stem') or '').strip()
        text = (entry.get('text') or '').strip()
        if not stem or not text:
            print(f'  [WARN] Skipping entry without stem/text: {entry!r}')
            continue
        if entry.get('enabled', True) is False:
            continue
        # Per-entry voice/model overrides take precedence over file-level defaults.
        result.append({
            'stem':  stem,
            'text':  text,
            'voice': entry.get('voice') or file_defaults.get('voice'),
            'model': entry.get('model') or file_defaults.get('model'),
        })
    return result


def _load_text_source(path: pathlib.Path) -> list[dict]:
    """
    Load prompts from a pipe-delimited text file.
    Each line: stem|text
    Lines starting with # or blank lines are ignored.
    """
    result: list[dict] = []
    for i, raw in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith('#'):
            continue
        if '|' not in line:
            print(f'  [WARN] Line {i}: skipping — expected stem|text, got: {line!r}')
            continue
        stem, _, text = line.partition('|')
        stem, text = stem.strip(), text.strip()
        if stem and text:
            result.append({'stem': stem, 'text': text, 'voice': None, 'model': None})
    return result


def _interactive_input() -> list[dict]:
    """
    Collect prompts interactively.
    Only called when stdin is a TTY and no file source was found.
    """
    print()
    print('No prompt source found.  Enter prompts interactively.')
    print('Format: stem|text   (blank line or Ctrl-D to finish)')
    print()
    result: list[dict] = []
    while True:
        try:
            raw = input('> ').strip()
        except EOFError:
            break
        if not raw:
            break
        if '|' not in raw:
            print('  Skipped — expected format: stem|text')
            continue
        stem, _, text = raw.partition('|')
        stem, text = stem.strip(), text.strip()
        if stem and text:
            result.append({'stem': stem, 'text': text, 'voice': None, 'model': None})
            print(f'  Added: {stem}')
    return result


def resolve_prompts(args: argparse.Namespace) -> list[dict]:
    """
    Return the ordered list of prompts to process.

    Priority:
      1. --input-file  (explicit override; JSON or stem|text)
      2. prompts.json  (default editable source, next to this script)
      3. Interactive   (TTY only, when no file source is available)
      4. Built-in defaults (always available fallback)
    """
    # 1. Explicit --input-file
    if args.input_file:
        p = pathlib.Path(args.input_file)
        if not p.exists():
            sys.exit(f'ERROR: --input-file not found: {p}')
        if p.suffix.lower() == '.json':
            prompts = _load_json_source(p)
        else:
            prompts = _load_text_source(p)
        print(f'Prompt source    : {p} ({len(prompts)} prompt(s), --input-file)')
        return prompts

    # 2. Auto-discover prompts.json next to this script
    auto_json = pathlib.Path(__file__).parent / 'prompts.json'
    if auto_json.exists():
        prompts = _load_json_source(auto_json)
        print(f'Prompt source    : {auto_json} ({len(prompts)} prompt(s), auto-discovered)')
        return prompts

    # 3. Interactive (only when stdin is a real TTY)
    if sys.stdin.isatty():
        prompts = _interactive_input()
        if prompts:
            print(f'Prompt source    : interactive ({len(prompts)} prompt(s))')
            return prompts

    # 4. Built-in defaults
    print(f'Prompt source    : built-in defaults ({len(BUILTIN_DEFAULTS)} prompt(s))')
    return [dict(p) for p in BUILTIN_DEFAULTS]


# ---------------------------------------------------------------------------
# Hash / cache
# ---------------------------------------------------------------------------

def compute_hash(
    text: str,
    voice: str,
    model: str,
    sample_rate: int,
    channels: int,
) -> str:
    """
    Stable SHA-256 fingerprint of every parameter that affects the audio output.
    If any one of these changes, the cache entry is invalidated and the prompt
    is regenerated on the next run.
    """
    blob = f'{text}|{voice}|{model}|{sample_rate}|{channels}'
    return hashlib.sha256(blob.encode('utf-8')).hexdigest()


def load_cache(output_dir: pathlib.Path) -> dict:
    cache_file = output_dir / CACHE_FILENAME
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding='utf-8'))
        except (json.JSONDecodeError, OSError):
            pass  # corrupt or unreadable — start fresh
    return {}


def save_cache(output_dir: pathlib.Path, cache: dict) -> None:
    cache_file = output_dir / CACHE_FILENAME
    try:
        cache_file.write_text(
            json.dumps(cache, indent=2, ensure_ascii=False),
            encoding='utf-8',
        )
    except OSError as exc:
        print(f'  [WARN] Could not write cache file: {exc}')


def needs_regen(
    cache: dict,
    stem: str,
    new_hash: str,
    formats: list[str],
    output_dir: pathlib.Path,
    force: bool,
) -> bool:
    """
    Return True when the prompt must be (re)generated:
      - --force was passed
      - stem has no cache entry (never generated)
      - stored hash differs from new_hash (text or settings changed)
      - any expected output file is missing from disk
    """
    if force:
        return True
    entry = cache.get(stem)
    if not entry:
        return True
    if entry.get('hash') != new_hash:
        return True
    # Verify every expected output file actually exists on disk.
    for fmt in formats:
        if not (output_dir / f'{stem}.{fmt}').exists():
            return True
    return False


# ---------------------------------------------------------------------------
# ffmpeg converters
# ---------------------------------------------------------------------------

def ffmpeg_check() -> None:
    """Exit early with a clear message if ffmpeg is not installed."""
    r = subprocess.run(['ffmpeg', '-version'], capture_output=True)
    if r.returncode != 0:
        sys.exit(
            'ERROR: ffmpeg is not installed.\n'
            '       Run:  sudo apt-get install -y ffmpeg'
        )


def _run_ffmpeg(extra_args: list[str]) -> None:
    r = subprocess.run(
        ['ffmpeg', '-y'] + extra_args,
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())


def to_wav(src: str, dst: str, sample_rate: int, channels: int) -> None:
    """PCM-16 WAV — universal Asterisk fallback format."""
    _run_ffmpeg([
        '-i', src,
        '-ar', str(sample_rate), '-ac', str(channels),
        '-acodec', 'pcm_s16le',
        dst,
    ])


def to_ulaw(src: str, dst: str, sample_rate: int, channels: int) -> None:
    """G.711 μ-law — raw headerless; Asterisk native for ulaw channels."""
    _run_ffmpeg([
        '-i', src,
        '-ar', str(sample_rate), '-ac', str(channels),
        '-acodec', 'pcm_mulaw', '-f', 'mulaw',
        dst,
    ])


def to_alaw(src: str, dst: str, sample_rate: int, channels: int) -> None:
    """G.711 A-law — raw headerless; Asterisk native for alaw channels."""
    _run_ffmpeg([
        '-i', src,
        '-ar', str(sample_rate), '-ac', str(channels),
        '-acodec', 'pcm_alaw', '-f', 'alaw',
        dst,
    ])


_CONVERTERS: dict = {
    'wav':  to_wav,
    'ulaw': to_ulaw,
    'alaw': to_alaw,
}


# ---------------------------------------------------------------------------
# Per-prompt generation
# ---------------------------------------------------------------------------

def generate_one(
    client,
    stem: str,
    text: str,
    voice: str,
    model: str,
    output_dir: pathlib.Path,
    formats: list[str],
    sample_rate: int,
    channels: int,
) -> dict[str, tuple]:
    """
    Fetch audio from OpenAI TTS and convert it to each requested format.

    Returns a dict: { format_name -> ('OK', file_size_bytes) | ('ERR', error_str) }
    The temp MP3 is always deleted, even on failure.
    """
    fmt_status: dict[str, tuple] = {}

    with tempfile.NamedTemporaryFile(suffix='.mp3', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        response = client.audio.speech.create(
            model=model,
            voice=voice,
            input=text,
            response_format='mp3',
        )
        response.stream_to_file(tmp_path)

        for fmt in formats:
            dst = str(output_dir / f'{stem}.{fmt}')
            try:
                _CONVERTERS[fmt](tmp_path, dst, sample_rate, channels)
                fmt_status[fmt] = ('OK', pathlib.Path(dst).stat().st_size)
            except Exception as exc:
                fmt_status[fmt] = ('ERR', str(exc))

    except Exception as exc:
        # TTS call itself failed — all formats fail
        for fmt in formats:
            fmt_status[fmt] = ('ERR', f'TTS error: {exc}')

    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

    return fmt_status


# ---------------------------------------------------------------------------
# Ownership  (optional, non-fatal)
# ---------------------------------------------------------------------------

def apply_ownership(output_dir: pathlib.Path, owner: str) -> None:
    """
    Run 'sudo chown -R <owner> <output_dir>'.
    Non-fatal: a warning is printed if the command fails, but generation
    results are not affected and the script does not exit.
    """
    r = subprocess.run(
        ['sudo', 'chown', '-R', owner, str(output_dir)],
        capture_output=True,
        text=True,
    )
    if r.returncode != 0:
        print(f'  [WARN] chown failed (non-fatal): {r.stderr.strip()}')
        print('         Set ownership manually if Asterisk cannot read the files.')
    else:
        print(f'  Ownership    : {owner} applied to {output_dir}')


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def _col(text: str, width: int) -> str:
    return f'{text:<{width}}'


def print_summary(results: list[dict], formats: list[str]) -> None:
    """Print a fixed-width ASCII summary table."""
    if not results:
        return

    w_stem   = max(len('Stem'),   max(len(r['stem'])   for r in results))
    w_status = max(len('Status'), len('CACHED'))   # = 6
    w_fmt    = max(len(f) for f in formats) + 2    # pad each format column
    w_hash   = 12                                   # short hash prefix

    fmt_header = '  '.join(_col(f.upper(), w_fmt) for f in formats)
    header  = (
        f"{_col('Stem', w_stem)}  "
        f"{_col('Status', w_status)}  "
        f"{fmt_header}  "
        f"{'Hash (prefix)'}"
    )
    divider = '-' * len(header)

    print()
    print(divider)
    print(header)
    print(divider)

    n_new = n_cached = n_error = 0
    for r in results:
        status     = r['status']
        hash_short = (r['hash'] or '')[:w_hash]
        fmt_cols   = []
        for fmt in formats:
            fs = r['formats'].get(fmt)
            if fs is None:
                fmt_cols.append(_col('-', w_fmt))
            elif fs[0] == 'OK':
                fmt_cols.append(_col('OK', w_fmt))
            else:
                fmt_cols.append(_col('ERR', w_fmt))

        if status == 'CACHED':
            n_cached += 1
        elif status == 'NEW':
            n_new += 1
        else:
            n_error += 1

        print(
            f"{_col(r['stem'], w_stem)}  "
            f"{_col(status, w_status)}  "
            f"{'  '.join(fmt_cols)}  "
            f"{hash_short}"
        )

    print(divider)
    total = len(results)
    print(
        f"{total} prompt(s)  |  "
        f"{n_new} generated  |  "
        f"{n_cached} cached  |  "
        f"{n_error} error(s)"
    )
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='generate_prompts.py',
        description=(
            'Generate telephony-native Asterisk audio prompts via OpenAI TTS.\n'
            'Prompts are loaded from --input-file, prompts.json, interactive\n'
            'input, or built-in defaults — whichever is available first.'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        '--input-file', metavar='PATH',
        help='JSON or stem|text file.  Takes priority over prompts.json.',
    )
    p.add_argument(
        '--output-dir', metavar='DIR', default=DEFAULT_OUTPUT_DIR,
        help=f'Directory to write audio files (default: {DEFAULT_OUTPUT_DIR})',
    )
    p.add_argument(
        '--sample-rate', type=int, default=DEFAULT_SAMPLE_RATE, metavar='HZ',
        help=f'Audio sample rate in Hz (default: {DEFAULT_SAMPLE_RATE})',
    )
    p.add_argument(
        '--channels', type=int, default=DEFAULT_CHANNELS, metavar='N',
        help=f'Audio channels — 1=mono, 2=stereo (default: {DEFAULT_CHANNELS})',
    )
    p.add_argument(
        '--voice', default=DEFAULT_VOICE,
        help=f'OpenAI TTS voice name (default: {DEFAULT_VOICE})',
    )
    p.add_argument(
        '--model', default=DEFAULT_MODEL,
        help=f'OpenAI TTS model (default: {DEFAULT_MODEL})',
    )
    p.add_argument(
        '--format-set', default=','.join(DEFAULT_FORMATS), metavar='FMT,...',
        help=f'Comma-separated output formats (default: {",".join(DEFAULT_FORMATS)})',
    )
    p.add_argument(
        '--only', metavar='STEM',
        help='Generate exactly one prompt by stem name; skip all others.',
    )
    p.add_argument(
        '--force', action='store_true',
        help='Ignore the cache and regenerate all selected prompts.',
    )
    p.add_argument(
        '--owner', metavar='USER:GROUP',
        help=(
            'Optional: apply "sudo chown -R USER:GROUP output_dir" after generation. '
            'Non-fatal if the command fails.'
        ),
    )
    return p


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = build_parser()
    args   = parser.parse_args()

    # ── Load API key ──────────────────────────────────────────────────────────
    _load_dotenv()
    api_key = os.environ.get('OPENAI_API_KEY', '')
    if not api_key:
        sys.exit(
            'ERROR: OPENAI_API_KEY is not set.\n'
            '       Export it or add it to the project .env file.'
        )

    # ── Parse and validate format-set ─────────────────────────────────────────
    formats = [f.strip().lower() for f in args.format_set.split(',') if f.strip()]
    unknown = [f for f in formats if f not in _CONVERTERS]
    if unknown:
        sys.exit(
            f'ERROR: Unknown format(s): {unknown}\n'
            f'       Supported: {list(_CONVERTERS.keys())}'
        )
    if not formats:
        sys.exit('ERROR: --format-set is empty.')

    # ── Validate ffmpeg before doing any work ─────────────────────────────────
    ffmpeg_check()

    # ── Output directory ──────────────────────────────────────────────────────
    output_dir = pathlib.Path(args.output_dir)
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        sys.exit(f'ERROR: Cannot create output directory {output_dir}: {exc}')

    # ── Print run configuration ───────────────────────────────────────────────
    print()
    print('=== Asterisk Prompt Generator ===')
    print(f'Output dir       : {output_dir}')
    print(f'Sample rate      : {args.sample_rate} Hz')
    print(f'Channels         : {args.channels}')
    print(f'Voice / model    : {args.voice} / {args.model}')
    print(f'Formats          : {", ".join(formats)}')
    print(f'Force regen      : {args.force}')
    if args.only:
        print(f'Filter (--only)  : {args.only}')
    print()

    # ── Resolve prompt list ───────────────────────────────────────────────────
    raw_prompts = resolve_prompts(args)

    if args.only:
        raw_prompts = [p for p in raw_prompts if p['stem'] == args.only]
        if not raw_prompts:
            sys.exit(f'ERROR: No prompt with stem {args.only!r} found in source.')

    if not raw_prompts:
        sys.exit('ERROR: No prompts to generate.')

    # ── Load cache ────────────────────────────────────────────────────────────
    cache = load_cache(output_dir)

    # ── Import OpenAI SDK ─────────────────────────────────────────────────────
    try:
        from openai import OpenAI
    except ImportError:
        sys.exit('ERROR: openai package not installed. Run:  pip install openai')

    client = OpenAI(api_key=api_key)

    # ── Generate ──────────────────────────────────────────────────────────────
    results: list[dict] = []

    for prompt in raw_prompts:
        stem  = prompt['stem']
        text  = prompt['text']
        voice = prompt.get('voice') or args.voice
        model = prompt.get('model') or args.model

        new_hash = compute_hash(text, voice, model, args.sample_rate, args.channels)

        if not needs_regen(cache, stem, new_hash, formats, output_dir, args.force):
            results.append({
                'stem':    stem,
                'status':  'CACHED',
                'hash':    new_hash,
                'formats': {fmt: ('OK', None) for fmt in formats},
            })
            continue

        print(f'  Generating [{stem}]  voice={voice}  model={model}')
        fmt_status = generate_one(
            client=client,
            stem=stem,
            text=text,
            voice=voice,
            model=model,
            output_dir=output_dir,
            formats=formats,
            sample_rate=args.sample_rate,
            channels=args.channels,
        )

        any_error = any(v[0] == 'ERR' for v in fmt_status.values() if v)
        status    = 'ERROR' if any_error else 'NEW'

        # Update cache only when generation fully succeeded.
        if not any_error:
            cache[stem] = {
                'hash':         new_hash,
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'voice':        voice,
                'model':        model,
                'sample_rate':  args.sample_rate,
                'channels':     args.channels,
                'formats':      formats,
            }

        results.append({
            'stem':    stem,
            'status':  status,
            'hash':    new_hash,
            'formats': fmt_status,
        })

    # ── Persist cache ─────────────────────────────────────────────────────────
    save_cache(output_dir, cache)

    # ── Summary table ─────────────────────────────────────────────────────────
    print_summary(results, formats)

    # ── Optional ownership (non-fatal) ────────────────────────────────────────
    if args.owner:
        apply_ownership(output_dir, args.owner)
    else:
        print(
            'Permissions note:\n'
            '  If Asterisk cannot read the generated files, set ownership explicitly:\n'
            f'    sudo chown -R <user>:<group> {output_dir}/\n'
            '  Use --owner <user>:<group> to apply this automatically on the next run.'
        )
        print()

    # ── Final status and next steps ───────────────────────────────────────────
    n_error = sum(1 for r in results if r['status'] == 'ERROR')
    n_new   = sum(1 for r in results if r['status'] == 'NEW')

    if n_error:
        print(f'{n_error} error(s) occurred.  Review the output above and re-run.')
        sys.exit(1)

    if n_new:
        print('New audio files written.  Reload the Asterisk dialplan:')
        print('  asterisk -rx "dialplan reload"')
    else:
        print('All prompts are up-to-date.  No Asterisk reload is needed.')


if __name__ == '__main__':
    main()
