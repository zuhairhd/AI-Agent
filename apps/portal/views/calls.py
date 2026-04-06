import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Q
from apps.voice_calls.models import CallSession
from apps.portal.serializers import CallSessionListSerializer, CallSessionDetailSerializer

logger = logging.getLogger(__name__)


class CallPaginator(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


@api_view(['GET'])
def calls_list_view(request):
    qs = CallSession.objects.prefetch_related('turns').order_by('-started_at')

    # Filters
    s = request.query_params.get('status')
    if s:
        qs = qs.filter(status=s)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(caller_number__icontains=search)

    needs_followup = request.query_params.get('needs_followup')
    if needs_followup is not None:
        qs = qs.filter(needs_followup=needs_followup.lower() == 'true')

    lang = request.query_params.get('language')
    if lang:
        qs = qs.filter(language=lang)

    date_from = request.query_params.get('date_from')
    date_to   = request.query_params.get('date_to')
    if date_from:
        qs = qs.filter(started_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(started_at__date__lte=date_to)

    paginator = CallPaginator()
    page      = paginator.paginate_queryset(qs, request)
    serializer = CallSessionListSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET', 'PATCH'])
def call_detail_view(request, pk):
    try:
        session = CallSession.objects.prefetch_related('turns').get(pk=pk)
    except CallSession.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(CallSessionDetailSerializer(session).data)

    # PATCH: allow updating staff_notes and needs_followup only
    allowed = ('staff_notes', 'needs_followup')
    data    = {k: v for k, v in request.data.items() if k in allowed}
    for attr, val in data.items():
        setattr(session, attr, val)
    session.save(update_fields=list(data.keys()))
    return Response(CallSessionDetailSerializer(session).data)
