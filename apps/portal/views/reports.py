import logging
from datetime import timedelta
from django.db.models import Count, Q
from django.utils.timezone import now
from rest_framework.decorators import api_view
from rest_framework.response import Response
from apps.voice_calls.models import CallSession

logger = logging.getLogger(__name__)


@api_view(['GET'])
def reports_view(request):
    period = request.query_params.get('period', '30d')
    days   = 7 if period == '7d' else (90 if period == '90d' else 30)
    start  = now() - timedelta(days=days)

    qs = CallSession.objects.filter(started_at__gte=start)

    total      = qs.count()
    resolved   = qs.filter(status=CallSession.Status.COMPLETED, needs_followup=False).count()
    unresolved = qs.filter(Q(status=CallSession.Status.FAILED) | Q(needs_followup=True)).count()
    followups  = qs.filter(needs_followup=True).count()
    escalated  = qs.filter(transfer_triggered=True).count()

    # Daily volume
    daily = {}
    for s in qs.values('started_at'):
        day = s['started_at'].date().isoformat()
        daily[day] = daily.get(day, 0) + 1
    daily_volume = [{'date': d, 'count': c} for d, c in sorted(daily.items())]

    # Language breakdown
    lang_breakdown = list(qs.values('language').annotate(count=Count('id')))

    return Response({
        'period':     period,
        'total':      total,
        'resolved':   resolved,
        'unresolved': unresolved,
        'followup_rate': round(followups / total, 3) if total else 0,
        'resolution_rate': round(resolved / total, 3) if total else 0,
        'escalated':  escalated,
        'daily_volume': daily_volume,
        'language_breakdown': lang_breakdown,
    })
