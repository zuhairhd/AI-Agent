import json
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.db.models import Count
from datetime import timedelta

from apps.voice_calls.models import CallRecord, CallEvent
from apps.rag_sync.models import KnowledgeDocument


@method_decorator(staff_member_required, name='dispatch')
class DashboardView(View):
    template_name = 'admin_panel/dashboard.html'

    def get(self, request):
        now = timezone.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=7)

        # Call stats
        total_today = CallRecord.objects.filter(created_at__gte=today_start).count()
        total_week = CallRecord.objects.filter(created_at__gte=week_start).count()

        status_counts = (
            CallRecord.objects.values('status')
            .annotate(count=Count('id'))
            .order_by('status')
        )
        status_data = {row['status']: row['count'] for row in status_counts}

        # Document stats
        doc_counts = (
            KnowledgeDocument.objects.values('sync_status')
            .annotate(count=Count('id'))
        )
        doc_data = {row['sync_status']: row['count'] for row in doc_counts}

        # Recent failed calls
        recent_failures = (
            CallRecord.objects.filter(status='failed')
            .prefetch_related('events')
            .order_by('-created_at')[:10]
        )

        # Recent calls
        recent_calls = CallRecord.objects.order_by('-created_at')[:15]

        context = {
            'total_today': total_today,
            'total_week': total_week,
            'status_data': json.dumps(status_data),
            'status_data_raw': status_data,
            'doc_data': json.dumps(doc_data),
            'doc_data_raw': doc_data,
            'recent_failures': recent_failures,
            'recent_calls': recent_calls,
            'docs_indexed': doc_data.get('indexed', 0),
            'docs_failed': doc_data.get('failed', 0),
            'docs_pending': doc_data.get('pending', 0),
        }
        return render(request, self.template_name, context)
