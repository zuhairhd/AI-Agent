"""
Django form for multi-file Knowledge Document upload.
Handles validation of file type and size before hitting the view.
"""
from django import forms
from .file_handler import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class DocumentUploadForm(forms.Form):
    """
    Multi-file upload form.
    Files are retrieved in the view with request.FILES.getlist('files').
    """
    files = forms.FileField(
        widget=MultipleFileInput(attrs={
            'accept': ','.join(ALLOWED_EXTENSIONS),
            'class': 'doc-file-input',
            'id': 'doc-files',
        }),
        label='Select files',
        help_text=(
            f"Allowed types: {', '.join(sorted(ALLOWED_EXTENSIONS))}. "
            f"Maximum size per file: {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB."
        ),
    )

    def clean_files(self):
        return self.cleaned_data.get('files')
