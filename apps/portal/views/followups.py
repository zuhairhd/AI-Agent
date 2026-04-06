import logging
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from apps.portal.models import FollowUp
from apps.portal.serializers import FollowUpSerializer

logger = logging.getLogger(__name__)


class FollowUpPaginator(PageNumberPagination):
    page_size = 20


@api_view(['GET', 'POST'])
def followups_list_view(request):
    if request.method == 'GET':
        qs = FollowUp.objects.select_related('session', 'alert', 'assigned_to').order_by('-created_at')

        s = request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)

        assigned = request.query_params.get('assigned_to')
        if assigned:
            qs = qs.filter(assigned_to_id=assigned)

        paginator = FollowUpPaginator()
        page      = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(FollowUpSerializer(page, many=True).data)

    # POST — create follow-up
    serializer = FollowUpSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
def followup_detail_view(request, pk):
    try:
        fu = FollowUp.objects.select_related('session', 'alert', 'assigned_to').get(pk=pk)
    except FollowUp.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(FollowUpSerializer(fu).data)

    allowed = ('status', 'priority', 'notes', 'due_date', 'completed_at', 'assigned_to')
    for k, v in request.data.items():
        if k in allowed:
            setattr(fu, k, v)
    fu.save()
    return Response(FollowUpSerializer(fu).data)
