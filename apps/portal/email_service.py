"""
Notification channel abstraction.

Adding SMS or WhatsApp later = implement one method on a new channel class.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.timezone import now

logger = logging.getLogger(__name__)


def build_notification_context(alert) -> dict:
    """Build template context dict from an Alert instance."""
    session = alert.session
    return {
        'alert':      alert,
        'session':    session,
        'caller':     session.caller_number if session else '—',
        'call_time':  session.started_at    if session else None,
        'status':     session.status        if session else '—',
        'portal_url': (
            f"{settings.PORTAL_BASE_URL}/portal/calls/{session.id}"
            if session else settings.PORTAL_BASE_URL
        ),
        'company':    getattr(settings, 'COMPANY_NAME', 'Future Smart Support'),
    }


class NotificationChannel:
    name: str = 'base'

    def send(self, alert, recipients: list) -> None:
        raise NotImplementedError


class EmailChannel(NotificationChannel):
    name = 'email'

    def send(self, alert, recipients: list) -> None:
        from apps.portal.models import Alert as AlertModel

        context = build_notification_context(alert)
        html_body = render_to_string('portal/email/alert_notification.html', context)
        text_body = render_to_string('portal/email/alert_notification.txt',  context)

        send_mail(
            subject=f"[FSS Alert] {alert.title}",
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipients,
            html_message=html_body,
            fail_silently=False,
        )

        AlertModel.objects.filter(pk=alert.pk).update(
            email_sent=True,
            email_sent_at=now(),
        )
        logger.info(f"[email_service] Email sent for alert {alert.id} to {recipients}")


class SMSChannel(NotificationChannel):
    name = 'sms'

    def send(self, alert, recipients: list) -> None:
        raise NotImplementedError("SMS channel not configured yet")


class WhatsAppChannel(NotificationChannel):
    name = 'whatsapp'

    def send(self, alert, recipients: list) -> None:
        raise NotImplementedError("WhatsApp channel not configured yet")


class NotificationDispatcher:
    def __init__(self, channels: list):
        self.channels = channels

    def dispatch(self, alert, recipients: list) -> None:
        for channel in self.channels:
            try:
                channel.send(alert, recipients)
            except NotImplementedError:
                pass  # channel not yet configured
            except Exception as exc:
                logger.error(f"[notify] {channel.name} failed for alert {alert.id}: {exc}")


def get_dispatcher() -> NotificationDispatcher:
    """Return the active dispatcher. Extend here to add SMS/WhatsApp later."""
    return NotificationDispatcher(channels=[EmailChannel()])
