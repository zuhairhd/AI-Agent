import logging
from django.utils.timezone import now
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from apps.portal.models import FollowUp, FollowUpActivity
from apps.portal.serializers import FollowUpSerializer

logger = logging.getLogger(__name__)


class FollowUpPaginator(PageNumberPagination):
    page_size = 20


@api_view(['GET', 'POST'])
def followups_list_view(request):
    if request.method == 'GET':
        qs = FollowUp.objects.select_related(
            'session', 'alert', 'assigned_to'
        ).prefetch_related('activities').order_by('-created_at')

        s = request.query_params.get('status')
        if s:
            qs = qs.filter(status=s)

        p = request.query_params.get('priority')
        if p:
            qs = qs.filter(priority=p)

        assigned = request.query_params.get('assigned_to')
        if assigned:
            qs = qs.filter(assigned_to_id=assigned)

        breached = request.query_params.get('sla_breached')
        if breached:
            qs = qs.filter(sla_breached=breached.lower() == 'true')

        paginator = FollowUpPaginator()
        page      = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(FollowUpSerializer(page, many=True).data)

    # POST — create follow-up
    serializer = FollowUpSerializer(data=request.data)
    if serializer.is_valid():
        fu = serializer.save()
        _log_activity(fu, request.user, 'status_changed', f'Follow-up created with status={fu.status}')
        return Response(FollowUpSerializer(fu).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET', 'PATCH'])
def followup_detail_view(request, pk):
    try:
        fu = FollowUp.objects.select_related(
            'session', 'alert', 'assigned_to'
        ).prefetch_related('activities').get(pk=pk)
    except FollowUp.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(FollowUpSerializer(fu).data)

    old_status   = fu.status
    old_assigned = fu.assigned_to_id
    allowed = ('status', 'priority', 'notes', 'due_date', 'completed_at', 'assigned_to')
    for k, v in request.data.items():
        if k in allowed:
            setattr(fu, k, v)

    if fu.status in ('completed', 'resolved', 'closed') and not fu.completed_at:
        fu.completed_at = now()

    fu.save()

    # Log status change
    if fu.status != old_status:
        _log_activity(fu, request.user, 'status_changed', f'{old_status} → {fu.status}')
    if fu.assigned_to_id != old_assigned:
        _log_activity(fu, request.user, 'assigned', f'Assigned to user_id={fu.assigned_to_id}')

    return Response(FollowUpSerializer(fu).data)


@api_view(['POST'])
def followup_claim_view(request, pk):
    """Allow current user to self-assign a follow-up."""
    try:
        fu = FollowUp.objects.get(pk=pk)
    except FollowUp.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    fu.assigned_to = request.user
    if fu.status == 'pending':
        fu.status = 'assigned'
    fu.save(update_fields=['assigned_to', 'status'])
    _log_activity(fu, request.user, 'claimed', f'Self-assigned by {request.user.username}')
    return Response(FollowUpSerializer(fu).data)


@api_view(['POST'])
def followup_add_note_view(request, pk):
    """Add a note to the activity log of a follow-up."""
    try:
        fu = FollowUp.objects.get(pk=pk)
    except FollowUp.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    note_text = request.data.get('note', '').strip()
    if not note_text:
        return Response({'detail': 'Note text is required.'}, status=status.HTTP_400_BAD_REQUEST)

    _log_activity(fu, request.user, 'note_added', note_text)
    return Response({'status': 'note added'})


def _log_activity(fu: FollowUp, user, action: str, description: str = '') -> None:
    try:
        FollowUpActivity.objects.create(
            followup=fu,
            user=user if (user and user.is_authenticated) else None,
            action=action,
            description=description,
        )
    except Exception as exc:
        logger.error(f"[followup_activity] Failed to log: {exc}")
