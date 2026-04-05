"""
Custom admin views for the rag_sync app.

Provides:
- DocumentUploadView: handles multi-file browser upload, validates files,
  saves them to COMPANY_DOCS_ROOT, creates DB records, and queues sync tasks.
"""
import logging

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views import View

from .file_handler import (
    DuplicateFileError,
    create_document_record,
    save_uploaded_file,
    validate_file,
)
from .forms import DocumentUploadForm

logger = logging.getLogger(__name__)


@method_decorator(staff_member_required, name='dispatch')
class DocumentUploadView(View):
    """
    Admin-accessible view for uploading one or multiple Knowledge Documents.
    Accessible at:  /admin/rag_sync/upload/
    """
    template_name = 'admin/rag_sync/upload.html'

    def get(self, request):
        form = DocumentUploadForm()
        return render(request, self.template_name, self._ctx(form))

    def post(self, request):
        form = DocumentUploadForm(request.POST, request.FILES)

        # Collect all uploaded files (multi-file input)
        uploaded_files = request.FILES.getlist('files')

        if not uploaded_files:
            messages.error(request, "No files were selected. Please choose at least one file.")
            return render(request, self.template_name, self._ctx(form))

        saved_count = 0
        skipped_count = 0
        error_count = 0

        for uploaded_file in uploaded_files:
            original_name = uploaded_file.name

            # --- Per-file validation ---
            errors = validate_file(uploaded_file, original_name)
            if errors:
                for err in errors:
                    messages.error(request, err)
                error_count += 1
                continue

            # --- Save to disk & create DB record ---
            try:
                file_info = save_uploaded_file(uploaded_file, original_name)
                doc = create_document_record(file_info)

                # Dispatch Celery sync task immediately
                try:
                    from tasks.sync_tasks import sync_document
                    sync_document.delay(doc.local_path)
                    logger.info(f"Queued sync task for document: {doc.id}")
                except Exception as celery_err:
                    # Sync failure is non-fatal — doc is saved, can be re-synced later
                    logger.warning(
                        f"Could not queue sync task for '{original_name}': {celery_err}"
                    )
                    messages.warning(
                        request,
                        f"'{original_name}' was saved but could not be queued for sync. "
                        f"Use 'Re-sync selected' from the document list."
                    )

                messages.success(
                    request,
                    f"'{original_name}' uploaded successfully ({doc.file_size_display})."
                )
                saved_count += 1

            except DuplicateFileError as exc:
                messages.warning(request, str(exc))
                skipped_count += 1

            except Exception as exc:
                logger.error(
                    f"Unexpected error saving '{original_name}': {exc}",
                    exc_info=True,
                )
                messages.error(
                    request,
                    f"'{original_name}': an unexpected error occurred. "
                    f"Please check server logs."
                )
                error_count += 1

        # Summary message
        parts = []
        if saved_count:
            parts.append(f"{saved_count} file(s) uploaded")
        if skipped_count:
            parts.append(f"{skipped_count} duplicate(s) skipped")
        if error_count:
            parts.append(f"{error_count} error(s)")
        if parts:
            logger.info(f"Upload session: {', '.join(parts)}")

        # Redirect to changelist so the user sees the new documents
        if saved_count > 0:
            return HttpResponseRedirect(
                reverse('admin:rag_sync_knowledgedocument_changelist')
            )

        # Stay on upload page if nothing was saved
        return render(request, self.template_name, self._ctx(form))

    @staticmethod
    def _ctx(form):
        return {
            'form': form,
            'title': 'Upload Knowledge Documents',
            'has_permission': True,
        }
