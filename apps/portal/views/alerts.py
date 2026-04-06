import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from apps.portal.models import Alert
from apps.portal.serializers import AlertSerializer
from apps.portal.tasks import send_alert_notification

logger = logging.getLogger(__name__)


class AlertPaginator(PageNumberPagination):
    page_size = 20


@api_view(['GET'])
def alerts_list_view(request):
    qs = Alert.objects.select_related('session', 'assigned_to').order_by('-created_at')

    s = request.query_params.get('status')
    if s:
        qs = qs.filter(status=s)

    t = request.query_params.get('type')
    if t:
        qs = qs.filter(alert_type=t)

    sev = request.query_params.get('severity')
    if sev:
        qs = qs.filter(severity=sev)

    paginator = AlertPaginator()
    page      = paginator.paginate_queryset(qs, request)
    return paginator.get_paginated_response(AlertSerializer(page, many=True).data)


@api_view(['GET', 'PATCH'])
def alert_detail_view(request, pk):
    try:
        alert = Alert.objects.select_related('session', 'assigned_to').get(pk=pk)
    except Alert.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(AlertSerializer(alert).data)

    allowed = ('status', 'assigned_to')
    for k, v in request.data.items():
        if k in allowed:
            setattr(alert, k, v)
    alert.save()
    return Response(AlertSerializer(alert).data)


@api_view(['POST'])
def resend_alert_email_view(request, pk):
    try:
        alert = Alert.objects.get(pk=pk)
    except Alert.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    # Reset sent flags so the task will send again
    Alert.objects.filter(pk=pk).update(email_sent=False, email_sent_at=None, send_email=True)
    alert.refresh_from_db()
    send_alert_notification.delay(str(alert.id))
    logger.info(f"[portal.alerts] Manual resend queued for alert {alert.id}")
    return Response({'detail': 'Resend queued'})
