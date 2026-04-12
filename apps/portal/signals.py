import logging
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.timezone import now, timedelta

logger = logging.getLogger(__name__)


# ── Auto-create NotificationPreference for every new user ────────────────────

@receiver(post_save, sender='auth.User')
def create_notification_preference_for_user(sender, instance, created, **kwargs):
    """
    Ensure every User has a NotificationPreference row with email_enabled=True.
    Fires on User creation; skips existing users to avoid overwriting their settings.
    """
    if not created:
        return
    try:
        from apps.portal.models import NotificationPreference
        _, was_created = NotificationPreference.objects.get_or_create(user=instance)
        if was_created:
            logger.info(
                "[portal.signals] Auto-created NotificationPreference for new user: %s (id=%s)",
                instance.username, instance.pk,
            )
    except Exception as exc:
        logger.error(
            "[portal.signals] Failed to auto-create NotificationPreference for user %s: %s",
            instance.pk, exc,
        )


# ── Evaluate alerts after every CallSession save ─────────────────────────────

@receiver(post_save, sender='voice_calls.CallSession')
def evaluate_call_alerts(sender, instance, created, **kwargs):
    """
    Inspect a CallSession after every save and create alerts if action is needed.
    Uses update() for any side-effect writes to avoid recursive signal triggers.

    Alert creation rules
    ────────────────────
    DROPPED_CALL     — status=FAILED
    HUMAN_REQUESTED  — transfer_triggered=True
    NO_ANSWER        — status=COMPLETED AND total_turns=0
    REPEATED_FAILURE — same caller has 2+ prior unresolved sessions in 7 days
    CALL_COMPLETED   — status in (COMPLETED, ENDED_BY_CALLER) AND total_turns>0
                       AND NOT transfer_triggered
                       AND (SiteConfig.notify_all_calls OR any user notify_all_calls)
    """
    # Import here to avoid circular at module load time
    from apps.portal.models import Alert
    from apps.voice_calls.models import CallSession
    from apps.portal.tasks import send_alert_notification

    session = instance

    logger.debug(
        "[portal.signals] evaluate_call_alerts | session=%s status=%s "
        "total_turns=%s transfer_triggered=%s needs_followup=%s",
        session.id, session.status, session.total_turns,
        session.transfer_triggered, session.needs_followup,
    )

    alerts_created = []       # problem alerts — will set needs_followup
    notify_only_alerts = []   # informational only — no needs_followup

    # ── 1. Failed / dropped call ─────────────────────────────────────────────
    if session.status == CallSession.Status.FAILED:
        if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.DROPPED_CALL).exists():
            a = Alert.objects.create(
                session=session,
                alert_type=Alert.AlertType.DROPPED_CALL,
                severity=Alert.Severity.HIGH,
                title=f"Call dropped — {session.caller_number}",
                description=(
                    f"Session {session.id} ended with status 'failed'. "
                    f"Reason: {session.failure_reason or 'unknown'}"
                ),
                send_email=True,
            )
            alerts_created.append(a)
            logger.info(
                "[portal.signals] Created DROPPED_CALL alert=%s for session=%s",
                a.id, session.id,
            )

    # ── 2. Transfer requested by caller ──────────────────────────────────────
    if session.transfer_triggered:
        if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.HUMAN_REQUESTED).exists():
            a = Alert.objects.create(
                session=session,
                alert_type=Alert.AlertType.HUMAN_REQUESTED,
                severity=Alert.Severity.HIGH,
                title=f"Human agent requested — {session.caller_number}",
                description=(
                    f"Session {session.id} triggered a transfer. "
                    f"Reason: {session.transfer_reason or 'unknown'}"
                ),
                send_email=True,
            )
            alerts_created.append(a)
            logger.info(
                "[portal.signals] Created HUMAN_REQUESTED alert=%s for session=%s",
                a.id, session.id,
            )

    # ── 3. Completed call with zero turns (caller gave up immediately) ────────
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
            logger.info(
                "[portal.signals] Created NO_ANSWER alert=%s for session=%s",
                a.id, session.id,
            )

    # ── 4. Repeated failures from same caller in last 7 days ─────────────────
    if session.status in (CallSession.Status.COMPLETED, CallSession.Status.FAILED):
        window_start = now() - timedelta(days=7)
        failed_count = CallSession.objects.filter(
            caller_number=session.caller_number,
            status__in=[CallSession.Status.FAILED, CallSession.Status.COMPLETED],
            needs_followup=True,
            started_at__gte=window_start,
        ).exclude(pk=session.pk).count()

        logger.debug(
            "[portal.signals] Repeated-failure check | session=%s caller=%s prior_count=%d",
            session.id, session.caller_number, failed_count,
        )

        if failed_count >= 2:
            if not Alert.objects.filter(session=session, alert_type=Alert.AlertType.REPEATED_FAILURE).exists():
                a = Alert.objects.create(
                    session=session,
                    alert_type=Alert.AlertType.REPEATED_FAILURE,
                    severity=Alert.Severity.HIGH,
                    title=f"Repeated failures — {session.caller_number}",
                    description=(
                        f"Caller has {failed_count + 1} unresolved sessions in the past 7 days."
                    ),
                    send_email=True,
                )
                alerts_created.append(a)
                logger.info(
                    "[portal.signals] Created REPEATED_FAILURE alert=%s for session=%s "
                    "(prior_count=%d)",
                    a.id, session.id, failed_count,
                )

    # ── 5. notify_all_calls: normal completed call ────────────────────────────
    # Covers COMPLETED and ENDED_BY_CALLER (caller hung up normally).
    # Excluded: transfer_triggered (HUMAN_REQUESTED alert handles those).
    # Excluded: total_turns==0 (NO_ANSWER alert handles those).
    if (
        session.status in (CallSession.Status.COMPLETED, CallSession.Status.ENDED_BY_CALLER)
        and session.total_turns > 0
        and not session.transfer_triggered
    ):
        from apps.portal.models import NotificationPreference, SiteConfig

        site_cfg = SiteConfig.get_solo()
        site_notify = site_cfg.notify_all_calls
        user_notify = NotificationPreference.objects.filter(
            email_enabled=True, notify_all_calls=True
        ).exists()

        logger.debug(
            "[portal.signals] notify_all_calls check | session=%s "
            "site_notify=%s user_notify=%s",
            session.id, site_notify, user_notify,
        )

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
                notify_only_alerts.append(a)
                logger.info(
                    "[portal.signals] Created CALL_COMPLETED alert=%s for session=%s "
                    "(triggered_by: site=%s user=%s)",
                    a.id, session.id, site_notify, user_notify,
                )
        else:
            logger.debug(
                "[portal.signals] CALL_COMPLETED skipped for session=%s: "
                "notify_all_calls is False (site and all users)",
                session.id,
            )

    # ── Mark session as needs_followup for problem alerts only ───────────────
    if alerts_created:
        CallSession.objects.filter(pk=session.pk).update(needs_followup=True)
        logger.info(
            "[portal.signals] Set needs_followup=True on session=%s "
            "(%d problem alert(s) created)",
            session.id, len(alerts_created),
        )

    # ── Queue email notifications (problem + informational) ──────────────────
    all_alerts = alerts_created + notify_only_alerts
    if not all_alerts:
        logger.debug(
            "[portal.signals] No alerts to queue for session=%s", session.id
        )
        return

    for alert in all_alerts:
        try:
            send_alert_notification.delay(str(alert.id))
            logger.info(
                "[portal.signals] Queued send_alert_notification for alert=%s "
                "(type=%s session=%s)",
                alert.id, alert.alert_type, session.id,
            )
        except Exception as exc:
            logger.error(
                "[portal.signals] Failed to queue notification for alert=%s: %s",
                alert.id, exc,
            )
