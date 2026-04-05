"""
Integration tests for the /api/call/ endpoint.
"""
import json
import uuid
from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse

from apps.voice_calls.models import CallRecord


class TestReceiveCallEndpoint(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = '/api/call/'

    def test_requires_post(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_missing_fields_returns_400(self):
        response = self.client.post(
            self.url,
            data=json.dumps({'caller_number': '1234567890'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)

    @patch('apps.asterisk_bridge.views.process_call')
    def test_valid_call_creates_record(self, mock_task):
        mock_task.delay.return_value = None
        response = self.client.post(
            self.url,
            data=json.dumps({
                'caller_number': '+15551234567',
                'audio_file_path': '/media/calls/test.wav',
            }),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 202)
        data = response.json()
        self.assertIn('call_id', data)
        self.assertEqual(data['status'], 'pending')

        call = CallRecord.objects.get(id=data['call_id'])
        self.assertEqual(call.caller_number, '+15551234567')
        self.assertEqual(call.status, 'pending')
        mock_task.delay.assert_called_once_with(data['call_id'])

    @patch('apps.asterisk_bridge.views.process_call')
    def test_valid_call_with_form_data(self, mock_task):
        mock_task.delay.return_value = None
        response = self.client.post(self.url, data={
            'caller_number': '+15550000001',
            'audio_file_path': '/media/calls/test2.wav',
        })
        self.assertEqual(response.status_code, 202)


class TestCallRecordModel(TestCase):
    def test_str_representation(self):
        call = CallRecord(caller_number='555-1234', status='answered')
        self.assertIn('555-1234', str(call))
        self.assertIn('answered', str(call))

    def test_default_status_is_pending(self):
        call = CallRecord(caller_number='555-0000', audio_file_path='/tmp/test.wav')
        self.assertEqual(call.status, 'pending')
