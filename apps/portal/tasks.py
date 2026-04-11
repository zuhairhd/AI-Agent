import logging
import os
import subprocess
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name="portal.send_alert_notification", bind=True, max_retries=3)
def send_alert_notification(self, alert_id: str) -> None:
    """
    Send email notification for an alert.

    Sends when alert.send_email is True.
    Recipients are collected from NotificationPreference records first,
    then env fallback, and always merged with SiteConfig.follow_up_emails.
    """
    from apps.portal.email_service import get_dispatcher
    from apps.portal.models import Alert, NotificationPreference

    try:
        alert = Alert.objects.select_related("session").get(pk=alert_id)
    except Alert.DoesNotExist:
        logger.warning(f"[portal.tasks] Alert {alert_id} not found; skipping notification")
        return

    if not alert.send_email:
        logger.debug(f"[portal.tasks] Alert {alert_id} has send_email=False; skipping")
        return

    recipients: list[str] = []

    # Per-user notification preferences
    prefs = NotificationPreference.objects.filter(email_enabled=True).select_related("user")
    for pref in prefs:
        if pref.notify_on and alert.alert_type not in pref.notify_on:
            continue

        addr = (pref.notify_email or getattr(pref.user, "email", "") or "").strip()
        if addr and addr not in recipients:
            recipients.append(addr)

    # Fallback to env-configured list
    if not recipients:
        env_emails = [
            e.strip()
            for e in getattr(settings, "PORTAL_NOTIFICATION_EMAILS", [])
            if e and e.strip()
        ]
        for addr in env_emails:
            if addr not in recipients:
                recipients.append(addr)

    # Always merge SiteConfig follow_up_emails
    try:
        from apps.portal.models import SiteConfig

        site_cfg = SiteConfig.get_solo()
        for addr in (site_cfg.follow_up_emails or []):
            addr = (addr or "").strip()
            if addr and addr not in recipients:
                recipients.append(addr)
    except Exception as exc:
        logger.warning(f"[portal.tasks] Could not read SiteConfig follow_up_emails: {exc}")

    if not recipients:
        logger.warning(f"[portal.tasks] No recipients for alert {alert_id}; email not sent")
        return

    try:
        get_dispatcher().dispatch(alert, recipients)
        logger.info(f"[portal.tasks] Alert {alert_id} emailed to: {recipients}")
    except Exception as exc:
        logger.error(f"[portal.tasks] Dispatch failed for alert {alert_id}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60)


def _run_ffmpeg(cmd: list[str], stem: str, label: str) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
        logger.info(f"[regenerate_prompt_audio] Built {label} for {stem}")
    except Exception as exc:
        logger.warning(f"[regenerate_prompt_audio] Failed building {label} for {stem}: {exc}")


def _build_asterisk_formats(wav_path: str, stem: str) -> tuple[str, str]:
    """
    Build telephony-friendly formats that Asterisk may prefer over .wav.

    Returns:
        (ulaw_path, alaw_path)
    """
    base_no_ext = os.path.splitext(wav_path)[0]
    ulaw_path = base_no_ext + ".ulaw"
    alaw_path = base_no_ext + ".alaw"

    # μ-law raw 8k mono
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            wav_path,
            "-ar",
            "8000",
            "-ac",
            "1",
            "-f",
            "mulaw",
            ulaw_path,
        ],
        stem,
        "ulaw",
    )

    # A-law raw 8k mono
    _run_ffmpeg(
        [
            "ffmpeg",
            "-y",
            "-i",
            wav_path,
            "-ar",
            "8000",
            "-ac",
            "1",
            "-f",
            "alaw",
            alaw_path,
        ],
        stem,
        "alaw",
    )

    return ulaw_path, alaw_path


@shared_task(name="portal.regenerate_prompt_audio", bind=True, max_retries=2)
def regenerate_prompt_audio(self, stem: str) -> None:
    """
    Async TTS regeneration for a CallPrompt triggered when its text is updated.

    This version writes:
    - <stem>.wav
    - <stem>.ulaw
    - <stem>.alaw

    so Asterisk will not keep using stale telephony formats.
    """
    from apps.portal.models import CallPrompt

    try:
        prompt = CallPrompt.objects.get(stem=stem)
    except CallPrompt.DoesNotExist:
        logger.warning(f"[regenerate_prompt_audio] stem={stem!r} not found; skipping")
        return

    sounds_dir = getattr(settings, "ASTERISK_SOUNDS_DIR", "/var/lib/asterisk/sounds/custom")
    os.makedirs(sounds_dir, exist_ok=True)

    wav_path = os.path.join(sounds_dir, f"{stem}.wav")
    tmp_raw_path = wav_path + ".openai.tmp"
    tmp_pcm_wav_path = wav_path + ".tmp.wav"

    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.OPENAI_API_KEY)

        # Step 1: generate base audio
        response = client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=prompt.text,
        )
        response.stream_to_file(tmp_raw_path)

        # Step 2: normalize WAV for telephony-friendly base source
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                tmp_raw_path,
                "-ar",
                "8000",
                "-ac",
                "1",
                "-c:a",
                "pcm_s16le",
                tmp_pcm_wav_path,
            ],
            check=True,
            capture_output=True,
        )
        os.replace(tmp_pcm_wav_path, wav_path)

        # Cleanup temp source
        if os.path.exists(tmp_raw_path):
            os.remove(tmp_raw_path)

        # Step 3: also build ulaw/alaw so Asterisk does not use stale old files
        ulaw_path, alaw_path = _build_asterisk_formats(wav_path, stem)

        prompt.audio_path = wav_path
        prompt.audio_exists = os.path.isfile(wav_path)
        prompt.version += 1
        prompt.save(update_fields=["audio_path", "audio_exists", "version"])

        logger.info(
            "[regenerate_prompt_audio] Done: %s | wav=%s ulaw=%s alaw=%s",
            stem,
            os.path.isfile(wav_path),
            os.path.isfile(ulaw_path),
            os.path.isfile(alaw_path),
        )

    except Exception as exc:
        # Best effort cleanup
        for path in [tmp_raw_path, tmp_pcm_wav_path]:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        logger.error(f"[regenerate_prompt_audio] Failed for {stem}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30)
