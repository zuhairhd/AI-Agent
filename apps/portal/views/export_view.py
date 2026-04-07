"""
Export and delete endpoints for calls and their associated media files.
"""
import io
import os
import logging
import zipfile
from django.http import HttpResponse, JsonResponse
from django.utils.timezone import now
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from apps.voice_calls.models import CallSession, ConversationTurn

logger = logging.getLogger(__name__)


@api_view(['GET'])
def export_call_view(request, pk):
    """
    GET /api/portal/calls/<pk>/export/
    Download a ZIP of the call's transcript text + any audio files.
    """
    try:
        session = CallSession.objects.prefetch_related('turns').get(pk=pk)
    except CallSession.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    buf  = io.BytesIO()
    name = f"call_{session.caller_number}_{session.started_at:%Y%m%d_%H%M%S}"

    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Transcript text
        lines = [
            f"Caller: {session.caller_number}",
            f"Started: {session.started_at}",
            f"Ended:   {session.ended_at or 'ongoing'}",
            f"Status:  {session.status}",
            f"Language: {session.language}",
            "---",
        ]
        for turn in session.turns.order_by('turn_number'):
            lines.append(f"\n[Turn {turn.turn_number}]")
            if turn.transcript_text:
                lines.append(f"Caller: {turn.transcript_text}")
            if turn.ai_response_text:
                lines.append(f"AI:     {turn.ai_response_text}")
        zf.writestr(f"{name}/transcript.txt", "\n".join(lines))

        # Audio files
        for turn in session.turns.order_by('turn_number'):
            for fpath, label in [
                (turn.audio_input_path,    f"turn{turn.turn_number}_caller"),
                (turn.audio_response_path, f"turn{turn.turn_number}_ai_response"),
            ]:
                if fpath and os.path.isfile(fpath):
                    ext = os.path.splitext(fpath)[1]
                    zf.write(fpath, f"{name}/audio/{label}{ext}")

    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="{name}.zip"'
    logger.info(f"[export] Exported call session={pk}")
    return response


@api_view(['DELETE'])
def delete_call_view(request, pk):
    """
    DELETE /api/portal/calls/<pk>/
    Delete call session + all associated audio files from disk.
    """
    try:
        session = CallSession.objects.prefetch_related('turns').get(pk=pk)
    except CallSession.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    # Remove audio files
    removed = []
    for turn in session.turns.all():
        for fpath in [turn.audio_input_path, turn.audio_response_path]:
            if fpath and os.path.isfile(fpath):
                try:
                    os.remove(fpath)
                    removed.append(fpath)
                except OSError as e:
                    logger.warning(f"[delete] Could not remove {fpath}: {e}")

    caller = session.caller_number
    session.delete()
    logger.info(f"[delete] Deleted session={pk} caller={caller} files_removed={len(removed)}")
    return Response({'deleted': True, 'files_removed': len(removed)})


@api_view(['DELETE'])
def delete_all_calls_view(request):
    """
    DELETE /api/portal/calls/
    Delete ALL call sessions and their audio files.
    Requires ?confirm=yes query parameter.
    """
    if request.query_params.get('confirm') != 'yes':
        return Response(
            {'detail': 'Add ?confirm=yes to confirm bulk deletion.'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    sessions = CallSession.objects.prefetch_related('turns').all()
    total_sessions = sessions.count()
    total_files    = 0

    for session in sessions:
        for turn in session.turns.all():
            for fpath in [turn.audio_input_path, turn.audio_response_path]:
                if fpath and os.path.isfile(fpath):
                    try:
                        os.remove(fpath)
                        total_files += 1
                    except OSError:
                        pass

    CallSession.objects.all().delete()
    logger.info(f"[delete_all] Deleted {total_sessions} sessions, {total_files} files")
    return Response({'deleted_sessions': total_sessions, 'deleted_files': total_files})
