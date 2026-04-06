"""
File handler utilities for KnowledgeDocument uploads.

Handles:
- Saving uploaded files to COMPANY_DOCS_ROOT with UUID-prefixed names
- SHA-256 computation for deduplication
- Creating/updating KnowledgeDocument records
- File deletion from disk
"""
import hashlib
import logging
import os
import uuid

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)

# Allowed MIME types and extensions for upload
ALLOWED_EXTENSIONS = {
    '.txt', '.pdf', '.docx', '.doc', '.md',
    '.csv', '.json', '.xlsx', '.xls', '.pptx', '.ppt',
    '.html', '.htm', '.rtf',
}

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB hard limit


def get_docs_root() -> str:
    """Return the absolute path to COMPANY_DOCS_ROOT, creating it if needed."""
    root = getattr(settings, 'COMPANY_DOCS_ROOT', '')
    if not root:
        raise ValueError("COMPANY_DOCS_ROOT is not configured in Django settings.")
    os.makedirs(root, exist_ok=True)
    return root


def compute_sha256(file_obj) -> str:
    """
    Compute SHA-256 of a file-like object.
    Resets the file pointer to the beginning before and after reading.
    """
    file_obj.seek(0)
    h = hashlib.sha256()
    for chunk in iter(lambda: file_obj.read(8192), b''):
        h.update(chunk)
    file_obj.seek(0)
    return h.hexdigest()


def safe_stored_filename(original_name: str) -> str:
    """
    Build a collision-safe filename:  <uuid>_<sanitised_original>
    Strips path separators and leading dots to prevent path traversal.
    """
    # Keep only the base name, replace spaces with underscores
    base = os.path.basename(original_name).replace(' ', '_')
    # Strip any leading dots (hidden file trick) but preserve extension
    base = base.lstrip('.')
    if not base:
        base = 'document'
    prefix = uuid.uuid4().hex[:8]
    return f"{prefix}_{base}"


def validate_file(file_obj, original_name: str) -> list[str]:
    """
    Validate extension and size.
    Returns a list of error strings (empty = valid).
    """
    errors = []
    _, ext = os.path.splitext(original_name)
    if ext.lower() not in ALLOWED_EXTENSIONS:
        allowed = ', '.join(sorted(ALLOWED_EXTENSIONS))
        errors.append(
            f"'{original_name}': unsupported file type '{ext}'. "
            f"Allowed types: {allowed}"
        )
    file_obj.seek(0, 2)  # seek to end
    size = file_obj.tell()
    file_obj.seek(0)
    if size > MAX_FILE_SIZE_BYTES:
        mb = MAX_FILE_SIZE_BYTES // (1024 * 1024)
        errors.append(
            f"'{original_name}': file is too large "
            f"({size / (1024*1024):.1f} MB). Maximum allowed: {mb} MB."
        )
    if size == 0:
        errors.append(f"'{original_name}': file is empty.")
    return errors


def save_uploaded_file(file_obj, original_name: str) -> dict:
    """
    Save an uploaded file to COMPANY_DOCS_ROOT.

    Returns a dict with:
        stored_name   - filename on disk (UUID-prefixed)
        local_path    - absolute path
        sha256        - hex digest
        file_size     - bytes
        original_name - original browser filename

    Raises ValueError if the file is a duplicate (same sha256 already on disk).
    """
    from apps.rag_sync.models import KnowledgeDocument

    docs_root = get_docs_root()

    # Compute hash first (used for dedup check)
    sha256 = compute_sha256(file_obj)

    # Deduplication: if an identical file already exists in DB, signal the caller
    existing = KnowledgeDocument.objects.filter(sha256=sha256).first()
    if existing:
        raise DuplicateFileError(
            f"This file is identical to an existing document: "
            f"'{existing.original_name or existing.file_name}' "
            f"(status: {existing.sync_status}). No changes made.",
            existing=existing,
        )

    stored_name = safe_stored_filename(original_name)
    dest_path = os.path.join(docs_root, stored_name)

    # Guard: ensure we stay inside docs_root (path traversal defence)
    dest_real = os.path.realpath(dest_path)
    root_real = os.path.realpath(docs_root)
    if not dest_real.startswith(root_real + os.sep):
        raise ValueError(f"Computed destination path escapes COMPANY_DOCS_ROOT: {dest_path}")

    # Determine file size
    file_obj.seek(0, 2)
    file_size = file_obj.tell()
    file_obj.seek(0)

    # Write to disk
    with open(dest_path, 'wb') as out:
        for chunk in iter(lambda: file_obj.read(65536), b''):
            out.write(chunk)

    logger.info(f"Saved uploaded file '{original_name}' → {dest_path} ({file_size} bytes)")

    return {
        'stored_name': stored_name,
        'local_path': dest_path,
        'sha256': sha256,
        'file_size': file_size,
        'original_name': original_name,
    }


def create_document_record(file_info: dict):
    """
    Create a KnowledgeDocument record from a saved file info dict.
    Returns the new KnowledgeDocument instance.
    """
    from apps.rag_sync.models import KnowledgeDocument

    doc = KnowledgeDocument.objects.create(
        file_name=file_info['stored_name'],
        original_name=file_info['original_name'],
        local_path=file_info['local_path'],
        file_size=file_info['file_size'],
        sha256=file_info['sha256'],
        sync_status=KnowledgeDocument.SyncStatus.PENDING,
    )
    logger.info(f"Created KnowledgeDocument record: {doc.id} for '{doc.original_name}'")
    return doc


def delete_document_from_disk(doc) -> bool:
    """
    Delete the physical file for a KnowledgeDocument.
    Returns True if deleted, False if file was already missing.
    """
    path = doc.local_path
    if path and os.path.exists(path):
        try:
            os.remove(path)
            logger.info(f"Deleted file from disk: {path}")
            return True
        except OSError as exc:
            logger.error(f"Could not delete file {path}: {exc}")
            raise
    logger.warning(f"File not found on disk (already removed?): {path}")
    return False


class DuplicateFileError(ValueError):
    """Raised when an uploaded file's SHA-256 matches an existing KnowledgeDocument."""
    def __init__(self, message, existing=None):
        super().__init__(message)
        self.existing = existing
