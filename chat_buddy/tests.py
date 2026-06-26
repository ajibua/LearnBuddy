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

import json
from .models import FlashcardDeck, Quiz, QuizQuestion, StudyMaterial

@override_settings(ALLOWED_HOSTS=['testserver', 'localhost', '127.0.0.1'], SECURE_SSL_REDIRECT=False)
class FlashcardAndQuizAPITests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='tester2', password='secret123')
		self.client.force_login(self.user)
		self.client.defaults['HTTP_HOST'] = 'localhost'
		self.material = StudyMaterial.objects.create(
			user=self.user,
			file_type='pdf',
			summary='This is a document summary.'
		)

	@patch('chat_buddy.ai_service.generate_flashcards_ai')
	def test_generate_flashcards_api_success(self, mock_generate_flashcards_ai):
		mock_generate_flashcards_ai.return_value = {
			'title': 'Test Deck',
			'cards': [
				{'front': 'Q1', 'back': 'A1'},
				{'front': 'Q2', 'back': 'A2'}
			]
		}
		response = self.client.post(
			'/api/flashcards/generate/',
			data=json.dumps({
				'material_id': self.material.id,
				'count': 2
			}),
			content_type='application/json'
		)
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIn('deck_id', data)
		self.assertEqual(data['title'], 'Test Deck')
		
		deck = FlashcardDeck.objects.get(id=data['deck_id'])
		self.assertEqual(deck.cards.count(), 2)
		self.assertEqual(deck.cards.first().front, 'Q1')

	@patch('chat_buddy.ai_service.generate_quiz_ai')
	def test_generate_quiz_api_success(self, mock_generate_quiz_ai):
		mock_generate_quiz_ai.return_value = {
			'title': 'Test Quiz',
			'questions': [
				{
					'question_text': 'Q1',
					'option_a': 'A', 'option_b': 'B', 'option_c': 'C', 'option_d': 'D',
					'correct_option': 'A',
					'explanation': 'E1'
				}
			]
		}
		response = self.client.post(
			'/api/quizzes/generate/',
			data=json.dumps({
				'material_id': self.material.id,
				'count': 1
			}),
			content_type='application/json'
		)
		self.assertEqual(response.status_code, 200)
		data = response.json()
		self.assertIn('quiz_id', data)
		self.assertEqual(data['title'], 'Test Quiz')

		quiz = Quiz.objects.get(id=data['quiz_id'])
		self.assertEqual(quiz.questions.count(), 1)
		question = quiz.questions.first()
		self.assertEqual(question.question_text, 'Q1')

		# Test submit answer api
		submit_response = self.client.post(
			f'/api/quizzes/submit/{quiz.id}/',
			data=json.dumps({
				'question_id': question.id,
				'user_answer': 'A'
			}),
			content_type='application/json'
		)
		self.assertEqual(submit_response.status_code, 200)
		question.refresh_from_db()
		self.assertEqual(question.user_answer, 'A')

		# Test get quiz api handles user_answer and ID
		get_response = self.client.get(f'/api/quizzes/quiz/{quiz.id}/')
		self.assertEqual(get_response.status_code, 200)
		get_data = get_response.json()
		self.assertEqual(get_data['questions'][0]['id'], question.id)
		self.assertEqual(get_data['questions'][0]['user_answer'], 'A')

		# Test finish quiz api computes score correctly
		finish_response = self.client.post(f'/api/quizzes/finish/{quiz.id}/')
		self.assertEqual(finish_response.status_code, 200)
		quiz.refresh_from_db()
		self.assertEqual(quiz.score, 1)
