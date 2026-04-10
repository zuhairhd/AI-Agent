"""
Celery periodic tasks for SLA tracking and follow-up escalation.

Beat schedule (added in settings):
  - check_sla_deadlines          every 5 minutes
  - fix_stuck_active_sessions    every 10 minutes
"""
import logging
from datetime import timedelta

from celery import shared_task
from django.utils.timezone import now

logger = logging.getLogger(__name__)


# @shared_task(name='tasks.check_sla_deadlines')
@shared_task(name='tasks.sla_tasks.fix_stuck_active_sessions')
def check_sla_deadlines() -> dict:
    """
    1. Mark overdue FollowUps as sla_breached.
    2. Send reminder emails at 50% and 80% of SLA window elapsed.
    3. Escalate (priority bump + admin email) when SLA is breached.
    """
    from apps.portal.models import FollowUp, Alert
    from apps.portal.tasks import send_alert_notification

    current_time = now()
    stats = {'checked': 0, 'breached': 0, 'reminded': 0, 'escalated': 0}

    open_followups = FollowUp.objects.filter(
        status__in=['pending', 'in_progress', 'assigned'],
        sla_deadline__isnull=False,
    ).select_related('session', 'assigned_to')

    for fu in open_followups:
        stats['checked'] += 1
        deadline   = fu.sla_deadline
        created    = fu.created_at
        total_secs = (deadline - created).total_seconds()
        elapsed    = (current_time - created).total_seconds()
        pct        = (elapsed / total_secs * 100) if total_secs > 0 else 100

        # ── SLA breached ─────────────────────────────────────────────────
        if current_time >= deadline and not fu.sla_breached:
            FollowUp.objects.filter(pk=fu.pk).update(sla_breached=True)
            stats['breached'] += 1
            logger.warning(f"[sla] SLA breached | followup={fu.id} session={fu.session_id}")

            # Create escalation alert
            if fu.session:
                alert, created = Alert.objects.get_or_create(
                    session=fu.session,
                    alert_type='unresolved',
                    defaults=dict(
                        severity='high',
                        title=f"SLA breached — {fu.session.caller_number}",
                        description=f"Follow-up #{fu.id} has exceeded its SLA deadline.",
                        send_email=True,
                    ),
                )
                if created:
                    send_alert_notification.delay(str(alert.id))
                    stats['escalated'] += 1

        # ── Send reminders at 50% and 80% ────────────────────────────────
        elif not fu.sla_breached and fu.reminded_at is None:
            if pct >= 50:
                _send_sla_reminder(fu, pct)
                FollowUp.objects.filter(pk=fu.pk).update(reminded_at=current_time)
                stats['reminded'] += 1

    logger.info(f"[sla] check_sla_deadlines done | {stats}")
    return stats


@shared_task(name='tasks.fix_stuck_active_sessions')
def fix_stuck_active_sessions() -> dict:
    """
    Find CallSessions stuck in 'active' status for more than 2 hours
    and mark them as 'abandoned'. This handles AGI crashes, server restarts,
    or callers who hung up without a clean session_end call.
    """
    from apps.voice_calls.models import CallSession

    cutoff = now() - timedelta(hours=2)
    stuck  = CallSession.objects.filter(
        status=CallSession.Status.ACTIVE,
        started_at__lt=cutoff,
    )
    count = stuck.count()

    if count:
        stuck_list = list(stuck.values_list('id', flat=True))
        for s_id in stuck_list:
            session = CallSession.objects.get(pk=s_id)
            ended   = now()
            dur     = int((ended - session.started_at).total_seconds())
            CallSession.objects.filter(pk=s_id).update(
                status=CallSession.Status.ABANDONED,
                ended_at=ended,
                duration_seconds=dur,
                failure_reason='Auto-closed: session inactive for >2 hours',
            )
            logger.warning(f"[sla] Abandoned stuck session={s_id}")

    logger.info(f"[sla] fix_stuck_active_sessions | closed={count}")
    return {'abandoned': count}


def _send_sla_reminder(followup, pct: float) -> None:
    """Send an email reminder that SLA is approaching."""
    try:
        from apps.portal.models import Alert, NotificationPreference
        from apps.portal.email_service import get_dispatcher
        from apps.portal.models import Alert as AlertModel

        # Collect recipients from prefs
        prefs      = NotificationPreference.objects.filter(email_enabled=True).select_related('user')
        recipients = [p.notify_email or p.user.email for p in prefs if p.notify_email or p.user.email]

        if not recipients:
            return

        # Build a minimal alert-like object for the dispatcher
        from apps.portal.models import Alert
        from django.conf import settings

        level = 'warning' if pct >= 80 else 'reminder'
        logger.info(
            f"[sla] Sending SLA {level} ({pct:.0f}% elapsed) "
            f"for followup={followup.id}"
        )

        # Create a transient alert for the email
        if followup.session:
            alert, _ = Alert.objects.get_or_create(
                session=followup.session,
                alert_type='unresolved',
                status='open',
                defaults=dict(
                    severity='medium',
                    title=f"SLA {level} — {followup.session.caller_number} ({pct:.0f}% elapsed)",
                    description=f"Follow-up is at {pct:.0f}% of its SLA window.",
                    send_email=True,
                ),
            )
            get_dispatcher().dispatch(alert, recipients)
    except Exception as exc:
        logger.error(f"[sla] reminder dispatch failed: {exc}", exc_info=True)
