import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now, timedelta

logger = logging.getLogger(__name__)


@receiver(post_save, sender='voice_calls.CallSession')
def evaluate_call_alerts(sender, instance, created, **kwargs):
    """
    Inspect a CallSession after every save and create alerts if action is needed.
    Uses update() for any side-effect writes to avoid recursive signal triggers.
    """
    # Import here to avoid circular at module load time
    from apps.portal.models import Alert
    from apps.voice_calls.models import CallSession
    from apps.portal.tasks import send_alert_notification

    session = instance
    alerts_created = []          # problem alerts — will set needs_followup
    notify_only_alerts = []      # informational only — no needs_followup

    # ── 1. Failed / dropped call ────────────────────────────────────────────
    if session.status == CallSession.Status.FAILED:
        if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.DROPPED_CALL).exists():
            a = Alert.objects.create(
                session=session,
                alert_type=Alert.AlertType.DROPPED_CALL,
                severity=Alert.Severity.HIGH,
                title=f"Call dropped — {session.caller_number}",
                description=f"Session {session.id} ended with status 'failed'. Reason: {session.failure_reason or 'unknown'}",
                send_email=True,
            )
            alerts_created.append(a)

    # ── 2. Transfer requested by caller ─────────────────────────────────────
    if session.transfer_triggered:
        if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.HUMAN_REQUESTED).exists():
            a = Alert.objects.create(
                session=session,
                alert_type=Alert.AlertType.HUMAN_REQUESTED,
                severity=Alert.Severity.HIGH,
                title=f"Human agent requested — {session.caller_number}",
                description=f"Session {session.id} triggered a transfer. Reason: {session.transfer_reason or 'unknown'}",
                send_email=True,
            )
            alerts_created.append(a)

    # ── 3. Completed call with zero turns (caller gave up immediately) ───────
    if session.status == CallSession.Status.COMPLETED and session.total_turns == 0:
        if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.NO_ANSWER).exists():
            a = Alert.objects.create(
                session=session,
                alert_type=Alert.AlertType.NO_ANSWER,
                severity=Alert.Severity.MEDIUM,
                title=f"No answer provided — {session.caller_number}",
                description=f"Session {session.id} completed but had 0 successful turns.",
                send_email=True,
            )
            alerts_created.append(a)

    # ── 4. Repeated failures from same caller in last 7 days ─────────────────
    if session.status in (CallSession.Status.COMPLETED, CallSession.Status.FAILED):
        window_start = now() - timedelta(days=7)
        failed_count = CallSession.objects.filter(
            caller_number=session.caller_number,
            status__in=[CallSession.Status.FAILED, CallSession.Status.COMPLETED],
            needs_followup=True,
            started_at__gte=window_start,
        ).exclude(pk=session.pk).count()

        if failed_count >= 2:
            if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.REPEATED_FAILURE).exists():
                a = Alert.objects.create(
                    session=session,
                    alert_type=Alert.AlertType.REPEATED_FAILURE,
                    severity=Alert.Severity.HIGH,
                    title=f"Repeated failures — {session.caller_number}",
                    description=f"Caller has {failed_count + 1} unresolved sessions in the past 7 days.",
                    send_email=True,
                )
                alerts_created.append(a)

    # ── 5. notify_all_calls: normal completed call ───────────────────────────
    if (
        session.status == CallSession.Status.COMPLETED
        and session.total_turns > 0
        and not session.transfer_triggered
    ):
        from apps.portal.models import NotificationPreference, SiteConfig
        site_cfg = SiteConfig.get_solo()
        site_notify = site_cfg.notify_all_calls
        user_notify = NotificationPreference.objects.filter(
            email_enabled=True, notify_all_calls=True
        ).exists()

        if site_notify or user_notify:
            if not Alert.objects.filter(
                session=session, alert_type=Alert.AlertType.CALL_COMPLETED
            ).exists():
                a = Alert.objects.create(
                    session=session,
                    alert_type=Alert.AlertType.CALL_COMPLETED,
                    severity=Alert.Severity.LOW,
                    title=f"Call completed — {session.caller_number}",
                    description=(
                        f"Session {session.id} completed normally "
                        f"with {session.total_turns} turn(s). "
                        f"Duration: {session.duration_seconds or 0}s."
                    ),
                    send_email=True,
                )
                notify_only_alerts.append(a)  # informational; does NOT set needs_followup

    # ── Mark session as needs_followup for problem alerts only ──────────────
    if alerts_created:
        CallSession.objects.filter(pk=session.pk).update(needs_followup=True)

    # ── Queue email notifications (both problem and informational) ────────────
    for alert in alerts_created + notify_only_alerts:
        try:
            send_alert_notification.delay(str(alert.id))
            logger.info(f"[portal.signals] Queued notification for alert {alert.id} ({alert.alert_type})")
        except Exception as exc:
            logger.error(f"[portal.signals] Failed to queue notification for alert {alert.id}: {exc}")
