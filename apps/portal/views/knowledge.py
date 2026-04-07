"""
Knowledge base (RAG) management views.
Upload, list, delete, re-sync KnowledgeDocument records.
"""
import hashlib
import logging
import os
import uuid

from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, parser_classes
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination

from apps.rag_sync.models import KnowledgeDocument

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt', 'csv', 'md'}


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            h.update(chunk)
    return h.hexdigest()


class KnowledgePaginator(PageNumberPagination):
    page_size = 20


@api_view(['GET'])
def knowledge_list_view(request):
    qs = KnowledgeDocument.objects.order_by('-created_at')

    status_filter = request.query_params.get('status')
    if status_filter:
        qs = qs.filter(sync_status=status_filter)

    search = request.query_params.get('search')
    if search:
        qs = qs.filter(original_name__icontains=search)

    paginator = KnowledgePaginator()
    page      = paginator.paginate_queryset(qs, request)
    data = [_doc_dict(d) for d in page]
    return paginator.get_paginated_response(data)


@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser])
def knowledge_upload_view(request):
    """
    POST /api/portal/knowledge/upload/
    Multipart: field name = 'file' (can repeat for multiple files).
    """
    files = request.FILES.getlist('file')
    if not files:
        return Response({'detail': 'No files provided.'}, status=status.HTTP_400_BAD_REQUEST)

    docs_root = getattr(settings, 'COMPANY_DOCS_ROOT', '')
    if not docs_root:
        return Response({'detail': 'COMPANY_DOCS_ROOT not configured.'}, status=500)

    os.makedirs(docs_root, exist_ok=True)
    results = []

    for uploaded in files:
        original = uploaded.name
        ext      = original.rsplit('.', 1)[-1].lower() if '.' in original else ''

        if ext not in ALLOWED_EXTENSIONS:
            results.append({'file': original, 'status': 'rejected', 'reason': f'Extension .{ext} not allowed'})
            continue

        # Save to disk with UUID prefix to avoid collisions
        stored_name = f"{uuid.uuid4().hex}_{original}"
        dest_path   = os.path.join(docs_root, stored_name)

        with open(dest_path, 'wb') as f:
            for chunk in uploaded.chunks():
                f.write(chunk)

        sha = _sha256(dest_path)
        size = os.path.getsize(dest_path)

        # Deduplication
        existing = KnowledgeDocument.objects.filter(sha256=sha).first()
        if existing:
            os.remove(dest_path)
            results.append({'file': original, 'status': 'duplicate', 'id': str(existing.id)})
            continue

        doc = KnowledgeDocument.objects.create(
            file_name=stored_name,
            original_name=original,
            local_path=dest_path,
            file_size=size,
            sha256=sha,
            sync_status=KnowledgeDocument.SyncStatus.PENDING,
        )

        # Queue sync task
        try:
            from tasks.sync_tasks import sync_document
            sync_document.delay(str(doc.id))
        except Exception as exc:
            logger.error(f"[knowledge] Failed to queue sync for {doc.id}: {exc}")

        results.append({'file': original, 'status': 'uploaded', 'id': str(doc.id)})
        logger.info(f"[knowledge] Uploaded {original} → {stored_name}")

    return Response({'results': results}, status=status.HTTP_201_CREATED)


@api_view(['DELETE'])
def knowledge_delete_view(request, pk):
    try:
        doc = KnowledgeDocument.objects.get(pk=pk)
    except KnowledgeDocument.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    # Remove from disk
    if doc.local_path and os.path.isfile(doc.local_path):
        try:
            os.remove(doc.local_path)
        except OSError as e:
            logger.warning(f"[knowledge] Could not delete file {doc.local_path}: {e}")

    doc.delete()
    logger.info(f"[knowledge] Deleted document id={pk}")
    return Response({'deleted': True})


@api_view(['POST'])
def knowledge_resync_view(request, pk):
    try:
        doc = KnowledgeDocument.objects.get(pk=pk)
    except KnowledgeDocument.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    doc.sync_status = KnowledgeDocument.SyncStatus.PENDING
    doc.save(update_fields=['sync_status'])

    try:
        from tasks.sync_tasks import sync_document
        sync_document.delay(str(doc.id))
    except Exception as exc:
        logger.error(f"[knowledge] Resync queue failed for {doc.id}: {exc}")
        return Response({'detail': 'Could not queue sync task.'}, status=500)

    return Response({'status': 'queued', 'id': str(doc.id)})


def _doc_dict(doc: KnowledgeDocument) -> dict:
    return {
        'id':            str(doc.id),
        'file_name':     doc.file_name,
        'original_name': doc.original_name,
        'local_path':    doc.local_path,
        'file_size':     doc.file_size,
        'file_size_display': doc.file_size_display,
        'file_extension': doc.file_extension,
        'sha256':        doc.sha256,
        'sync_status':   doc.sync_status,
        'openai_file_id': doc.openai_file_id,
        'vector_store_id': doc.vector_store_id,
        'last_synced_at': doc.last_synced_at.isoformat() if doc.last_synced_at else None,
        'error_message': doc.error_message,
        'created_at':    doc.created_at.isoformat(),
    }
