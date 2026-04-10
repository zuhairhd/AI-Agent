import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='portal.send_alert_notification', bind=True, max_retries=3)
def send_alert_notification(self, alert_id: str) -> None:
    """
    Send email notification for an alert.
    Only sends if alert.send_email is True.
    Recipients are collected from NotificationPreference records.
    Falls back to PORTAL_NOTIFICATION_EMAILS setting if no prefs exist.
    """
    from apps.portal.models import Alert, NotificationPreference
    from apps.portal.email_service import get_dispatcher

    try:
        alert = Alert.objects.select_related('session').get(pk=alert_id)
    except Alert.DoesNotExist:
        logger.warning(f"[portal.tasks] Alert {alert_id} not found; skipping notification")
        return

    if not alert.send_email:
        logger.debug(f"[portal.tasks] Alert {alert_id} has send_email=False; skipping")
        return

    # Collect recipients from per-user preferences
    prefs = NotificationPreference.objects.filter(email_enabled=True).select_related('user')
    recipients = []
    for pref in prefs:
        # Empty notify_on means all types; otherwise check membership
        if pref.notify_on and alert.alert_type not in pref.notify_on:
            continue
        addr = pref.notify_email or pref.user.email
        if addr:
            recipients.append(addr)

    # Fallback: use env-configured list
    if not recipients:
        env_emails = [e.strip() for e in getattr(settings, 'PORTAL_NOTIFICATION_EMAILS', []) if e.strip()]
        recipients = env_emails

    if not recipients:
        logger.warning(f"[portal.tasks] No recipients for alert {alert_id}; email not sent")
        return

    try:
        get_dispatcher().dispatch(alert, recipients)
    except Exception as exc:
        logger.error(f"[portal.tasks] Dispatch failed for alert {alert_id}: {exc}")
        raise self.retry(exc=exc, countdown=60)


@shared_task(name='portal.regenerate_prompt_audio', bind=True, max_retries=2)
def regenerate_prompt_audio(self, stem: str) -> None:
    """
    Async TTS regeneration for a CallPrompt triggered when its text is updated.
    Mirrors the synchronous logic in prompt_regenerate_view.
    """
    import os
    from django.conf import settings as _settings
    from apps.portal.models import CallPrompt

    try:
        prompt = CallPrompt.objects.get(stem=stem)
    except CallPrompt.DoesNotExist:
        logger.warning(f"[regenerate_prompt_audio] stem={stem!r} not found; skipping")
        return

    sounds_dir = getattr(_settings, 'ASTERISK_SOUNDS_DIR', '/var/lib/asterisk/sounds/custom')
    os.makedirs(sounds_dir, exist_ok=True)
    wav_path = os.path.join(sounds_dir, f"{stem}.wav")

    try:
        from openai import OpenAI
        client   = OpenAI(api_key=_settings.OPENAI_API_KEY)
        response = client.audio.speech.create(model='tts-1', voice='alloy', input=prompt.text)
        response.stream_to_file(wav_path)

        try:
            import subprocess
            tmp = wav_path + '.tmp.wav'
            subprocess.run(
                ['ffmpeg', '-y', '-i', wav_path, '-ar', '8000', '-ac', '1', '-f', 'wav', tmp],
                check=True, capture_output=True,
            )
            os.replace(tmp, wav_path)
        except Exception as fe:
            logger.warning(f"[regenerate_prompt_audio] ffmpeg skipped for {stem}: {fe}")

        prompt.audio_path   = wav_path
        prompt.audio_exists = os.path.isfile(wav_path)
        prompt.version     += 1
        prompt.save(update_fields=['audio_path', 'audio_exists', 'version'])
        logger.info(f"[regenerate_prompt_audio] Done: {stem}")

    except Exception as exc:
        logger.error(f"[regenerate_prompt_audio] Failed for {stem}: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=30)
