import os
from django.db import models
from apps.core.models import TimeStampedModel


class KnowledgeDocument(TimeStampedModel):
    class SyncStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        UPLOADING = 'uploading', 'Uploading'
        INDEXED = 'indexed', 'Indexed'
        FAILED = 'failed', 'Failed'

    # Stored filename on disk (UUID-prefixed to avoid collisions)
    file_name = models.CharField(max_length=256)

    # Original filename as seen in the browser — shown in the UI
    original_name = models.CharField(max_length=256, blank=True, default='')

    # Absolute path on the server under COMPANY_DOCS_ROOT
    local_path = models.CharField(max_length=512)

    # File size in bytes — populated at upload time
    file_size = models.PositiveBigIntegerField(null=True, blank=True)

    # SHA-256 hash — used for deduplication
    sha256 = models.CharField(max_length=64, unique=True, db_index=True)

    openai_file_id = models.CharField(max_length=128, blank=True, null=True, db_index=True)
    vector_store_id = models.CharField(max_length=128, blank=True, null=True)
    sync_status = models.CharField(
        max_length=16,
        choices=SyncStatus.choices,
        default=SyncStatus.PENDING,
        db_index=True,
    )
    last_synced_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'knowledge_documents'
        ordering = ['-created_at']
        verbose_name = 'Knowledge Document'
        verbose_name_plural = 'Knowledge Documents'

    def __str__(self):
        display = self.original_name or self.file_name
        return f"{display} [{self.sync_status}]"

    @property
    def file_extension(self):
        """Return the file extension in uppercase, e.g. 'PDF'."""
        _, ext = os.path.splitext(self.original_name or self.file_name)
        return ext.lstrip('.').upper() if ext else 'UNKNOWN'

    @property
    def file_size_display(self):
        """Human-readable file size."""
        if self.file_size is None:
            return '-'
        size = float(self.file_size)
        for unit in ('B', 'KB', 'MB', 'GB'):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == 'B' else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"
