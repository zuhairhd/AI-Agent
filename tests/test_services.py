"""
Unit tests for OpenAI service layer.
All external calls are mocked — no real API calls made.
"""
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open
from django.test import TestCase, override_settings


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_VECTOR_STORE_ID='vs_test123',
)
class TestOpenAIFileService(TestCase):
    def test_upload_file_returns_id(self):
        with patch('services.openai_file_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.files.create.return_value = MagicMock(id='file-abc123')

            with tempfile.NamedTemporaryFile(suffix='.txt', delete=False) as f:
                f.write(b'test content')
                path = f.name

            try:
                from services.openai_file_service import upload_file
                result = upload_file(path)
                self.assertEqual(result, 'file-abc123')
                mock_client.files.create.assert_called_once()
            finally:
                os.unlink(path)

    def test_delete_file_returns_true(self):
        with patch('services.openai_file_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            from services.openai_file_service import delete_file
            result = delete_file('file-abc123')
            self.assertTrue(result)
            mock_client.files.delete.assert_called_once_with('file-abc123')


@override_settings(
    OPENAI_API_KEY='test-key',
    OPENAI_VECTOR_STORE_ID='vs_test123',
)
class TestOpenAIVectorStoreService(TestCase):
    def test_ensure_vector_store_returns_env_id(self):
        from services.openai_vector_store_service import ensure_vector_store
        result = ensure_vector_store()
        self.assertEqual(result, 'vs_test123')

    def test_check_status_completed(self):
        with patch('services.openai_vector_store_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.beta.vector_stores.files.retrieve.return_value = MagicMock(status='completed')
            from services.openai_vector_store_service import check_status
            result = check_status('vs_test', 'file-123')
            self.assertEqual(result, 'completed')

    def test_check_status_failed(self):
        with patch('services.openai_vector_store_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.beta.vector_stores.files.retrieve.return_value = MagicMock(status='failed')
            from services.openai_vector_store_service import check_status
            result = check_status('vs_test', 'file-123')
            self.assertEqual(result, 'failed')


@override_settings(OPENAI_API_KEY='test-key')
class TestTranscriptionService(TestCase):
    def test_transcribe_returns_text(self):
        with patch('services.openai_transcription_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            mock_client.audio.transcriptions.create.return_value = 'Hello, I need help with my order.'

            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                f.write(b'fake wav data')
                path = f.name

            try:
                from services.openai_transcription_service import transcribe
                result = transcribe(path)
                self.assertEqual(result, 'Hello, I need help with my order.')
            finally:
                os.unlink(path)

    def test_transcribe_raises_if_file_missing(self):
        from services.openai_transcription_service import transcribe
        with self.assertRaises(FileNotFoundError):
            transcribe('/nonexistent/path/audio.wav')


@override_settings(OPENAI_API_KEY='test-key')
class TestResponseService(TestCase):
    def test_query_rag_returns_answer(self):
        with patch('services.openai_response_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            content_block = MagicMock()
            content_block.text = 'Our return policy is 30 days.'
            output_item = MagicMock()
            output_item.content = [content_block]
            mock_client.responses.create.return_value = MagicMock(output=[output_item])

            from services.openai_response_service import query_rag
            result = query_rag('What is the return policy?', 'vs_test')
            self.assertEqual(result, 'Our return policy is 30 days.')

    def test_query_rag_returns_fallback_on_empty(self):
        with patch('services.openai_response_service.OpenAI') as MockOpenAI:
            mock_client = MockOpenAI.return_value
            output_item = MagicMock()
            output_item.content = []
            mock_client.responses.create.return_value = MagicMock(output=[output_item])

            from services.openai_response_service import query_rag, FALLBACK_RESPONSE
            result = query_rag('Unknown question', 'vs_test')
            self.assertEqual(result, FALLBACK_RESPONSE)
