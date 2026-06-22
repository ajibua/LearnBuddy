from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.test.utils import override_settings

from .ai_service import ask_buddy
from .models import ChatMessage, ChatSession

@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'], SECURE_SSL_REDIRECT=False)
class FileUploadViewTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='tester', password='secret123')
		self.client.force_login(self.user)
		self.client.defaults['HTTP_HOST'] = 'localhost'

	@patch('chat_buddy.views.summarize_pdf', return_value='Short PDF summary')
	def test_upload_links_material_to_existing_session(self, summarize_pdf_mock):
		session = ChatSession.objects.create(user=self.user)
		upload = SimpleUploadedFile('lesson.pdf', b'%PDF-1.4 test content', content_type='application/pdf')

		response = self.client.post(
			'/api/upload/',
			data={
				'file': upload,
				'session_id': str(session.id),
				'user_message': 'Explain the main idea',
			},
		)

		self.assertEqual(response.status_code, 201)
		session.refresh_from_db()
		self.assertIsNotNone(session.study_material)
		self.assertEqual(session.study_material.user, self.user)
		self.assertEqual(session.study_material.summary, 'Short PDF summary')
		self.assertEqual(ChatMessage.objects.filter(session=session, role='user').count(), 1)
		self.assertEqual(ChatMessage.objects.filter(session=session, role='assistant').count(), 1)
		summarize_pdf_mock.assert_called_once()

	@patch('chat_buddy.views.summarize_document', return_value='Plain text summary')
	def test_upload_accepts_text_documents(self, summarize_document_mock):
		upload = SimpleUploadedFile('notes.txt', b'Latest class notes', content_type='text/plain')

		response = self.client.post('/api/upload/', data={'file': upload})

		self.assertEqual(response.status_code, 201)
		payload = response.json()
		self.assertEqual(payload['file_type'], 'document')
		self.assertEqual(payload['summary'], 'Plain text summary')
		summarize_document_mock.assert_called_once()
