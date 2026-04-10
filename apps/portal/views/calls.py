import csv
import io
import logging
import os

from django.http import FileResponse, HttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from apps.voice_calls.models import CallSession, ConversationTurn
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


@api_view(['GET'])
def recording_serve_view(request, pk, turn_id):
    """
    GET /api/portal/calls/<pk>/recording/<turn_id>/?type=input|response
    Serve caller recording or AI response audio for in-browser playback.
    Returns 404 if the file is not on disk.
    """
    try:
        session = CallSession.objects.get(pk=pk)
    except CallSession.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    try:
        turn = session.turns.get(pk=turn_id)
    except ConversationTurn.DoesNotExist:
        return Response({'detail': 'Turn not found'}, status=status.HTTP_404_NOT_FOUND)

    audio_type = request.query_params.get('type', 'response')
    path = turn.audio_input_path if audio_type == 'input' else turn.audio_response_path

    if not path or not os.path.isfile(path):
        return Response({'detail': 'Audio not available'}, status=status.HTTP_404_NOT_FOUND)

    logger.info(f"[recording_serve] session={pk} turn={turn_id} type={audio_type}")
    return FileResponse(open(path, 'rb'), content_type='audio/wav', filename=os.path.basename(path))


@api_view(['POST'])
def bulk_delete_view(request):
    """
    POST /api/portal/calls/bulk-delete/
    Body: { "ids": ["uuid1", "uuid2", ...] }
    Deletes the selected sessions and their audio files from disk.
    """
    ids = request.data.get('ids', [])
    if not ids:
        return Response({'detail': 'No ids provided.'}, status=status.HTTP_400_BAD_REQUEST)

    sessions = CallSession.objects.prefetch_related('turns').filter(pk__in=ids)
    removed_files = 0
    for sess in sessions:
        for turn in sess.turns.all():
            for fpath in [turn.audio_input_path, turn.audio_response_path]:
                if fpath and os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                        removed_files += 1
                    except OSError as e:
                        logger.warning(f"[bulk_delete] Could not remove {fpath}: {e}")

    deleted_count, _ = CallSession.objects.filter(pk__in=ids).delete()
    logger.info(f"[bulk_delete] Deleted {deleted_count} sessions, {removed_files} files")
    return Response({'deleted': deleted_count, 'files_removed': removed_files})


@api_view(['POST'])
def bulk_mark_view(request):
    """
    POST /api/portal/calls/bulk-mark/
    Body: { "ids": [...], "needs_followup": true }
    """
    ids = request.data.get('ids', [])
    needs_followup = request.data.get('needs_followup', True)
    if not ids:
        return Response({'detail': 'No ids provided.'}, status=status.HTTP_400_BAD_REQUEST)
    updated = CallSession.objects.filter(pk__in=ids).update(needs_followup=needs_followup)
    return Response({'updated': updated})


@api_view(['GET'])
def calls_export_csv_view(request):
    """
    GET /api/portal/calls/export-csv/
    Export calls matching current filter params as CSV (metadata only, no audio).
    """
    qs = CallSession.objects.order_by('-started_at')

    flt_status = request.query_params.get('status')
    if flt_status:
        qs = qs.filter(status=flt_status)
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

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        'id', 'caller_number', 'started_at', 'ended_at', 'status',
        'language', 'total_turns', 'duration_seconds',
        'needs_followup', 'transfer_triggered', 'failure_reason',
    ])
    for row in qs:
        writer.writerow([
            str(row.id), row.caller_number,
            row.started_at.isoformat() if row.started_at else '',
            row.ended_at.isoformat()   if row.ended_at   else '',
            row.status, row.language, row.total_turns,
            row.duration_seconds or '',
            row.needs_followup, row.transfer_triggered,
            row.failure_reason or '',
        ])

    response = HttpResponse(buf.getvalue(), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="calls_export.csv"'
    return response
