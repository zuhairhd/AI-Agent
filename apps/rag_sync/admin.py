"""
Django Admin configuration for the rag_sync app.

Registers KnowledgeDocument with:
- Rich list display (original name, type badge, size, status badge, dates)
- Bulk actions: re-sync, delete from disk
- Custom "Upload Documents" button in the changelist header
- Read-only detail view showing all metadata
"""
import logging

from django.contrib import admin, messages
from django.urls import path, reverse
from django.utils.html import format_html

from .models import KnowledgeDocument

logger = logging.getLogger(__name__)


@admin.register(KnowledgeDocument)
class KnowledgeDocumentAdmin(admin.ModelAdmin):
    # ------------------------------------------------------------------
    # List display
    # ------------------------------------------------------------------
    list_display = (
        'display_name',
        'type_badge',
        'file_size_display_col',
        'sync_status_badge',
        'last_synced_at',
        'openai_file_id_short',
        'created_at',
    )
    list_display_links = ('display_name',)
    list_filter = ('sync_status', 'created_at')
    search_fields = ('original_name', 'file_name', 'local_path', 'openai_file_id')
    ordering = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'created_at'

    # ------------------------------------------------------------------
    # Detail view — most fields are read-only; sync_status is editable
    # ------------------------------------------------------------------
    readonly_fields = (
        'id',
        'original_name',
        'file_name',
        'local_path',
        'file_size_display_col',
        'file_extension_display',
        'sha256',
        'openai_file_id',
        'vector_store_id',
        'last_synced_at',
        'created_at',
        'updated_at',
        'error_message',
    )

    fieldsets = (
        ('Document', {
            'fields': (
                'id',
                'original_name',
                'file_name',
                'local_path',
                'file_size_display_col',
                'file_extension_display',
                'sha256',
            ),
        }),
        ('OpenAI / Vector Store Sync', {
            'fields': (
                'sync_status',
                'openai_file_id',
                'vector_store_id',
                'last_synced_at',
            ),
        }),
        ('Error Details', {
            'fields': ('error_message',),
            'classes': ('collapse',),
            'description': 'Populated when sync_status is "failed".',
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    # ------------------------------------------------------------------
    # Bulk actions
    # ------------------------------------------------------------------
    actions = ['action_resync', 'action_delete_with_file']

    @admin.action(description='Re-sync selected documents with OpenAI')
    def action_resync(self, request, queryset):
        """Reset sync status to pending and queue a Celery sync task per doc."""
        from tasks.sync_tasks import sync_document

        count = 0
        for doc in queryset:
            doc.sync_status = KnowledgeDocument.SyncStatus.PENDING
            doc.error_message = None
            doc.save(update_fields=['sync_status', 'error_message'])
            try:
                sync_document.delay(doc.local_path)
                count += 1
            except Exception as exc:
                logger.error(f"Could not queue sync for {doc.id}: {exc}")
                self.message_user(
                    request,
                    f"Could not queue '{doc.original_name or doc.file_name}': {exc}",
                    messages.WARNING,
                )
        if count:
            self.message_user(
                request,
                f"{count} document(s) queued for re-sync.",
                messages.SUCCESS,
            )

    @admin.action(description='Delete selected documents (DB record + disk file)')
    def action_delete_with_file(self, request, queryset):
        """Delete DB records and physically remove the file from COMPANY_DOCS_ROOT."""
        from .file_handler import delete_document_from_disk

        deleted_db = 0
        deleted_disk = 0
        for doc in queryset:
            name = doc.original_name or doc.file_name
            try:
                removed = delete_document_from_disk(doc)
                if removed:
                    deleted_disk += 1
            except OSError as exc:
                self.message_user(
                    request,
                    f"Could not delete file for '{name}' from disk: {exc}",
                    messages.WARNING,
                )
            doc.delete()
            deleted_db += 1
            logger.info(f"Admin deleted document: {name}")

        self.message_user(
            request,
            f"{deleted_db} record(s) deleted from database, "
            f"{deleted_disk} file(s) removed from disk.",
            messages.SUCCESS,
        )

    # ------------------------------------------------------------------
    # Custom URL: the upload view lives inside Django's admin namespace
    # ------------------------------------------------------------------
    def get_urls(self):
        from .views import DocumentUploadView
        urls = super().get_urls()
        custom = [
            path(
                'upload/',
                self.admin_site.admin_view(DocumentUploadView.as_view()),
                name='rag_sync_knowledgedocument_upload',
            ),
        ]
        # Prepend so our URL is matched before the default <pk>/change/
        return custom + urls

    # ------------------------------------------------------------------
    # Changelist: inject "Upload Documents" button via custom template
    # ------------------------------------------------------------------
    change_list_template = 'admin/rag_sync/knowledgedocument/change_list.html'

    # ------------------------------------------------------------------
    # List display column methods
    # ------------------------------------------------------------------
    @admin.display(description='Document Name', ordering='original_name')
    def display_name(self, obj):
        name = obj.original_name or obj.file_name
        return format_html(
            '<span title="Path: {}" style="font-weight:500;">{}</span>',
            obj.local_path, name,
        )

    @admin.display(description='Type')
    def type_badge(self, obj):
        ext = obj.file_extension
        color_map = {
            'PDF': '#ef4444', 'DOCX': '#3b82f6', 'DOC': '#3b82f6',
            'TXT': '#6b7280', 'MD': '#8b5cf6', 'CSV': '#10b981',
            'JSON': '#f59e0b', 'XLSX': '#059669', 'XLS': '#059669',
            'PPTX': '#f97316', 'PPT': '#f97316',
            'HTML': '#06b6d4', 'HTM': '#06b6d4', 'RTF': '#9ca3af',
        }
        color = color_map.get(ext, '#6b7280')
        return format_html(
            '<span style="background:{};color:#fff;padding:1px 8px;border-radius:4px;'
            'font-size:10px;font-weight:700;letter-spacing:0.05em;">{}</span>',
            color, ext,
        )

    @admin.display(description='Size', ordering='file_size')
    def file_size_display_col(self, obj):
        return obj.file_size_display

    @admin.display(description='File Type')
    def file_extension_display(self, obj):
        return obj.file_extension

    @admin.display(description='Sync Status', ordering='sync_status')
    def sync_status_badge(self, obj):
        colors = {
            'pending':   '#f59e0b',
            'uploading': '#3b82f6',
            'indexed':   '#10b981',
            'failed':    '#ef4444',
        }
        icons = {
            'pending': '⏳',
            'uploading': '⬆',
            'indexed': '✓',
            'failed': '✕',
        }
        color = colors.get(obj.sync_status, '#6b7280')
        icon = icons.get(obj.sync_status, '')
        return format_html(
            '<span style="background:{};color:#fff;padding:2px 10px;border-radius:100px;'
            'font-size:11px;font-weight:600;white-space:nowrap;">'
            '{} {}</span>',
            color, icon, obj.sync_status.upper(),
        )

    @admin.display(description='OpenAI File ID')
    def openai_file_id_short(self, obj):
        if obj.openai_file_id:
            return format_html(
                '<span title="{}" style="font-family:monospace;font-size:11px;">'
                '{}\u2026</span>',
                obj.openai_file_id,
                obj.openai_file_id[:18],
            )
        return format_html('<span style="color:#9ca3af;">\u2014</span>')
