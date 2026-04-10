import hashlib
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from celery import shared_task
from django.utils import timezone as django_timezone

from apps.rag_sync.models import KnowledgeDocument
from services.openai_file_service import upload_file, delete_file
from services.openai_vector_store_service import ensure_vector_store, attach_file, check_status

logger = logging.getLogger(__name__)


def compute_sha256(file_path: str) -> str:
    h = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_kwargs={'max_retries': 3},
    retry_backoff=True,
    retry_backoff_max=60,
    name='tasks.sync_document',
)
#def sync_document(self, file_path: str) -> dict:
def sync_document(self, value: str) -> dict:
    """
    Sync a document from disk to OpenAI Vector Store.
    Idempotent: skips if sha256 already indexed.
    """
    logger.info(f"Starting sync for: {value}")
    file_path = value

#    if not Path(file_path).exists():
#        # Try resolving as document id
#        try:
#            from apps.portal.models import KnowledgeDocument  # adjust model name if different
#            doc = KnowledgeDocument.objects.get(id=value)
#            file_path = doc.file.path   # or doc.local_path depending on your model
#        except Exception as e:
#            logger.error(f"File does not exist and doc lookup failed: {value} | {e}")
#            return {"status": "skipped", "reason": "file_not_found"}

    if not Path(file_path).exists():
       try:
           doc = KnowledgeDocument.objects.get(id=value)
           file_path = doc.local_path
       except KnowledgeDocument.DoesNotExist:
           logger.error(f"Document ID not found: {value}")
           return {"status": "skipped", "reason": "document_not_found"}
       except Exception as e:
           logger.error(f"File does not exist and doc lookup failed: {value} | {e}")
           return {"status": "skipped", "reason": "file_not_found"}

    if not Path(file_path).exists():
        logger.error(f"Resolved path still missing: {file_path}")
        return {"status": "skipped", "reason": "file_not_found"}


#    if not os.path.exists(file_path):
#        logger.error(f"File does not exist: {file_path}")
#        return {'status': 'skipped', 'reason': 'file_not_found'}

    file_name = os.path.basename(file_path)
    sha256 = compute_sha256(file_path)

    # Idempotency check
    existing = KnowledgeDocument.objects.filter(sha256=sha256, sync_status='indexed').first()
    if existing:
        logger.info(f"File already indexed (sha256={sha256[:12]}...). Skipping.")
        return {'status': 'skipped', 'reason': 'already_indexed', 'id': str(existing.id)}

    # Create or update DB record
    doc, created = KnowledgeDocument.objects.update_or_create(
        sha256=sha256,
        defaults={
            'file_name': file_name,
            'local_path': file_path,
            'sync_status': KnowledgeDocument.SyncStatus.UPLOADING,
            'error_message': None,
        }
    )

    try:
        # Step 1: Upload file
        openai_file_id = upload_file(file_path)
        doc.openai_file_id = openai_file_id
        doc.sync_status = KnowledgeDocument.SyncStatus.UPLOADING
        doc.save(update_fields=['openai_file_id', 'sync_status'])

        # Step 2: Ensure vector store exists
        vector_store_id = ensure_vector_store()

        # Step 3: Attach file to vector store
        attach_file(vector_store_id, openai_file_id)

        # Step 4: Poll until indexed
        final_status = check_status(vector_store_id, openai_file_id)
        if final_status != 'completed':
            raise RuntimeError(f"Indexing did not complete: status={final_status}")

        # Step 5: Persist success
        doc.vector_store_id = vector_store_id
        doc.sync_status = KnowledgeDocument.SyncStatus.INDEXED
        doc.last_synced_at = django_timezone.now()
        doc.error_message = None
        doc.save(update_fields=['vector_store_id', 'sync_status', 'last_synced_at', 'error_message'])

        logger.info(f"Document synced successfully: {file_name} (openai_file_id={openai_file_id})")
        return {'status': 'indexed', 'file_name': file_name, 'openai_file_id': openai_file_id}

    except Exception as exc:
        logger.error(f"Sync failed for {file_path}: {exc}", exc_info=True)
        doc.sync_status = KnowledgeDocument.SyncStatus.FAILED
        doc.error_message = str(exc)
        doc.save(update_fields=['sync_status', 'error_message'])
        raise  # triggers Celery autoretry
