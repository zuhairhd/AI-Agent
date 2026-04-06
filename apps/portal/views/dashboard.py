import logging
from datetime import timedelta
from django.db.models import Count, Q
from django.utils.timezone import now
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.voice_calls.models import CallSession
from apps.portal.models import Alert

logger = logging.getLogger(__name__)


@api_view(['GET'])
def dashboard_view(request):
    """
    Returns KPIs, hourly volume, status breakdown, recent alerts, recent calls.
    Filtered to today by default; honours ?date_from and ?date_to query params.
    """
    today_start = now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = today_start + timedelta(days=1)

    sessions_today = CallSession.objects.filter(started_at__gte=today_start, started_at__lt=today_end)

    total_today      = sessions_today.count()
    resolved_today   = sessions_today.filter(status=CallSession.Status.COMPLETED, needs_followup=False).count()
    unresolved_today = sessions_today.filter(
        Q(status=CallSession.Status.FAILED) | Q(needs_followup=True)
    ).count()
    followup_today   = sessions_today.filter(needs_followup=True).count()
    escalated_today  = sessions_today.filter(transfer_triggered=True).count()

    # Duration average (in seconds) for sessions with both start and end
    completed_with_time = sessions_today.filter(ended_at__isnull=False)
    avg_duration = None
    if completed_with_time.exists():
        from django.db.models import Avg, F, ExpressionWrapper, DurationField
        result = completed_with_time.annotate(
            dur=ExpressionWrapper(F('ended_at') - F('started_at'), output_field=DurationField())
        ).aggregate(avg=Avg('dur'))
        if result['avg']:
            avg_duration = int(result['avg'].total_seconds())

    # Hourly call volume for today (0–23)
    hourly = {}
    for s in sessions_today.values('started_at'):
        h = s['started_at'].hour
        hourly[h] = hourly.get(h, 0) + 1
    hourly_volume = [{'hour': h, 'count': hourly.get(h, 0)} for h in range(24)]

    # Status breakdown (all time last 30 days)
    thirty_ago = now() - timedelta(days=30)
    status_breakdown = list(
        CallSession.objects.filter(started_at__gte=thirty_ago)
        .values('status')
        .annotate(count=Count('id'))
    )

    # Recent open alerts
    from apps.portal.serializers import AlertSerializer, CallSessionListSerializer
    recent_alerts = Alert.objects.filter(status=Alert.Status.OPEN).order_by('-created_at')[:5]
    recent_calls  = CallSession.objects.prefetch_related('turns').order_by('-started_at')[:5]

    return Response({
        'kpis': {
            'total_today':      total_today,
            'resolved_today':   resolved_today,
            'unresolved_today': unresolved_today,
            'followup_today':   followup_today,
            'escalated_today':  escalated_today,
            'avg_duration_seconds': avg_duration,
        },
        'hourly_volume':    hourly_volume,
        'status_breakdown': status_breakdown,
        'recent_alerts':    AlertSerializer(recent_alerts, many=True).data,
        'recent_calls':     CallSessionListSerializer(recent_calls, many=True).data,
    })
