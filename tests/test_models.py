"""
Model-level tests for KnowledgeDocument and CallEvent.
"""
from django.test import TestCase
from apps.voice_calls.models import CallRecord, CallEvent
from apps.rag_sync.models import KnowledgeDocument
import uuid


class TestKnowledgeDocument(TestCase):
    def test_str_representation(self):
        doc = KnowledgeDocument(file_name='policy.pdf', sync_status='indexed')
        self.assertIn('policy.pdf', str(doc))
        self.assertIn('indexed', str(doc))

    def test_sha256_unique(self):
        sha = 'a' * 64
        KnowledgeDocument.objects.create(
            file_name='doc1.txt',
            local_path='/company_docs/doc1.txt',
            sha256=sha,
        )
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            KnowledgeDocument.objects.create(
                file_name='doc2.txt',
                local_path='/company_docs/doc2.txt',
                sha256=sha,
            )

    def test_default_sync_status_is_pending(self):
        doc = KnowledgeDocument(file_name='test.txt', sha256='b' * 64)
        self.assertEqual(doc.sync_status, 'pending')


class TestCallEvent(TestCase):
    def setUp(self):
        self.call = CallRecord.objects.create(
            caller_number='+15551234567',
            audio_file_path='/media/calls/test.wav',
        )

    def test_create_event(self):
        event = CallEvent.objects.create(
            call=self.call,
            event_type='started',
            payload={'task_id': 'abc-123'},
        )
        self.assertEqual(event.event_type, 'started')
        self.assertEqual(event.payload['task_id'], 'abc-123')

    def test_event_cascade_delete(self):
        CallEvent.objects.create(call=self.call, event_type='started')
        call_id = self.call.id
        self.call.delete()
        self.assertEqual(CallEvent.objects.filter(call_id=call_id).count(), 0)
