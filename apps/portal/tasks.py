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

    Recipient resolution — four levels, in order:

    1. NotificationPreference records (email_enabled=True)
       - For CALL_COMPLETED alerts: include user only if SiteConfig.notify_all_calls=True
         OR the user's own notify_all_calls=True.
       - For all other types: apply per-user notify_on type filter (empty list = receive all).
    2. PORTAL_NOTIFICATION_EMAILS env var — used as fallback when level 1 yields nothing.
    3. SiteConfig.follow_up_emails — always merged into final list.
    4. SiteConfig.contact_email — final safety-net if all other sources are empty.

    Any address that is blank or already in the list is skipped (deduplication).
    """
    from apps.portal.email_service import get_dispatcher
    from apps.portal.models import Alert, NotificationPreference, SiteConfig

    # ── Fetch alert ──────────────────────────────────────────────────────────
    try:
        alert = Alert.objects.select_related("session").get(pk=alert_id)
    except Alert.DoesNotExist:
        logger.warning("[portal.tasks] Alert %s not found; skipping notification", alert_id)
        return

    if not alert.send_email:
        logger.info("[portal.tasks] Alert %s has send_email=False; skipping", alert_id)
        return

    # ── Load global config ───────────────────────────────────────────────────
    try:
        site_cfg = SiteConfig.get_solo()
    except Exception as exc:
        logger.error("[portal.tasks] Cannot load SiteConfig: %s", exc)
        site_cfg = None

    is_call_completed = (alert.alert_type == Alert.AlertType.CALL_COMPLETED)
    site_notify_all = bool(site_cfg and site_cfg.notify_all_calls)

    logger.info(
        "[portal.tasks] Resolving recipients for alert=%s type=%s "
        "is_call_completed=%s site_notify_all=%s",
        alert_id, alert.alert_type, is_call_completed, site_notify_all,
    )

    recipients: list[str] = []

    # ── Level 1: Per-user preferences ────────────────────────────────────────
    prefs = NotificationPreference.objects.filter(email_enabled=True).select_related("user")
    pref_count = 0
    for pref in prefs:
        pref_count += 1

        if is_call_completed:
            # CALL_COMPLETED: only include if global flag is on OR user opted in
            if not site_notify_all and not pref.notify_all_calls:
                logger.debug(
                    "[portal.tasks] Skip user_id=%s for CALL_COMPLETED: "
                    "site_notify_all=False and user notify_all_calls=False",
                    pref.user_id,
                )
                continue
        else:
            # All other types: apply per-user type filter (empty list = all types)
            if pref.notify_on and alert.alert_type not in pref.notify_on:
                logger.debug(
                    "[portal.tasks] Skip user_id=%s: alert_type=%s not in notify_on=%s",
                    pref.user_id, alert.alert_type, pref.notify_on,
                )
                continue

        addr = (pref.notify_email or getattr(pref.user, "email", "") or "").strip()
        if addr and addr not in recipients:
            recipients.append(addr)
            logger.debug(
                "[portal.tasks] + user recipient: %s (user_id=%s)", addr, pref.user_id
            )
        elif not addr:
            logger.warning(
                "[portal.tasks] User %s (id=%s) has no email address; "
                "set an address in their profile or NotificationPreference.notify_email",
                getattr(pref.user, "username", "?"), pref.user_id,
            )

    logger.info(
        "[portal.tasks] Level-1 done: %d prefs scanned, %d recipients so far",
        pref_count, len(recipients),
    )

    # ── Level 2: Env fallback (only when level 1 produced nothing) ───────────
    if not recipients:
        env_emails: list[str] = [
            e.strip()
            for e in getattr(settings, "PORTAL_NOTIFICATION_EMAILS", [])
            if e and e.strip()
        ]
        for addr in env_emails:
            if addr not in recipients:
                recipients.append(addr)
        if env_emails:
            logger.info(
                "[portal.tasks] Level-2 env fallback applied: %s", env_emails
            )
        else:
            logger.debug(
                "[portal.tasks] Level-2 PORTAL_NOTIFICATION_EMAILS is empty; no-op"
            )

    # ── Level 3: Always merge SiteConfig.follow_up_emails ────────────────────
    if site_cfg:
        added_fu: list[str] = []
        for addr in (site_cfg.follow_up_emails or []):
            addr = (addr or "").strip()
            if addr and addr not in recipients:
                recipients.append(addr)
                added_fu.append(addr)
        if added_fu:
            logger.info(
                "[portal.tasks] Level-3 merged SiteConfig.follow_up_emails: %s", added_fu
            )

    # ── Level 4: Final fallback — SiteConfig.contact_email ───────────────────
    if not recipients and site_cfg and site_cfg.contact_email:
        addr = site_cfg.contact_email.strip()
        if addr:
            recipients.append(addr)
            logger.warning(
                "[portal.tasks] Level-4 safety-net: no other recipients configured for "
                "alert %s; using SiteConfig.contact_email=%s. "
                "Fix: add email to a user profile, or set SiteConfig.follow_up_emails.",
                alert_id, addr,
            )

    if not recipients:
        logger.warning(
            "[portal.tasks] No recipients resolved for alert %s (type=%s); "
            "email NOT sent. To fix: (a) ensure staff users have email addresses and "
            "NotificationPreference records, (b) set SiteConfig.follow_up_emails, "
            "or (c) set SiteConfig.contact_email as a catch-all.",
            alert_id, alert.alert_type,
        )
        return

    logger.info(
        "[portal.tasks] Dispatching alert %s (type=%s) to %d recipient(s): %s",
        alert_id, alert.alert_type, len(recipients), recipients,
    )

    try:
        get_dispatcher().dispatch(alert, recipients)
        logger.info("[portal.tasks] Alert %s dispatched successfully to: %s", alert_id, recipients)
    except Exception as exc:
        logger.error(
            "[portal.tasks] Dispatch failed for alert %s: %s",
            alert_id, exc, exc_info=True,
        )
        raise self.retry(exc=exc, countdown=60)


# ── Audio helpers ─────────────────────────────────────────────────────────────

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
