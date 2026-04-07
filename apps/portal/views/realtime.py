"""
Simple polling endpoint for real-time call monitoring.
Returns summary of active sessions + recent changes in the last N seconds.
"""
import logging
from datetime import timedelta
from django.utils.timezone import now
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.voice_calls.models import CallSession
from apps.portal.serializers import CallSessionListSerializer

logger = logging.getLogger(__name__)


@api_view(['GET'])
def realtime_summary_view(request):
    """
    GET /api/portal/realtime/
    Returns active sessions + sessions updated in the last 30 seconds.
    Frontend polls this every 5–10 s to drive the live monitor.
    """
    window_secs = int(request.query_params.get('window', 30))
    cutoff      = now() - timedelta(seconds=window_secs)

    active  = CallSession.objects.prefetch_related('turns').filter(status='active')
    recent  = CallSession.objects.prefetch_related('turns').filter(
        updated_at__gte=cutoff
    ).exclude(status='active')

    return Response({
        'ts':     now().isoformat(),
        'active': CallSessionListSerializer(active, many=True).data,
        'recent': CallSessionListSerializer(recent, many=True).data,
    })
