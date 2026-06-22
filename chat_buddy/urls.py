from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/signup/', views.signup_view, name='signup'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('chat/', views.chat_view, name='chat'),
    path('dashboard/', views.dashboard_view, name='dashboard'),
    path('flashcards/', views.flashcards_view, name='flashcards'),
    path('quizzes/', views.quizzes_view, name='quizzes'),
    
    path('api/chat/', views.chat_api, name='chat-api'),
    path('api/upload/', views.FileUploadView.as_view(), name='upload-file'),
    path('api/chat-history/', views.get_chat_history, name='chat-history'),
    path('api/current-user/', views.get_current_user, name='current-user'),
    path('api/feedback/<int:message_id>/', views.feedback_api, name='feedback'),
    path('api/regenerate/', views.regenerate_api, name='regenerate'),
    
    path('api/flashcards/generate/', views.generate_flashcards_api, name='api-flashcards-generate'),
    path('api/flashcards/list/', views.list_flashcard_decks_api, name='api-flashcards-list'),
    path('api/flashcards/deck/<int:deck_id>/', views.get_flashcard_deck_api, name='api-flashcards-deck'),
    
    path('api/quizzes/generate/', views.generate_quiz_api, name='api-quizzes-generate'),
    path('api/quizzes/list/', views.list_quizzes_api, name='api-quizzes-list'),
    path('api/quizzes/quiz/<int:quiz_id>/', views.get_quiz_api, name='api-quizzes-quiz'),
    path('api/quizzes/submit/<int:quiz_id>/', views.submit_quiz_answer_api, name='api-quizzes-submit'),
    path('api/quizzes/finish/<int:quiz_id>/', views.finish_quiz_api, name='api-quizzes-finish'),
    path('api/analytics/track/', views.track_study_time_api, name='api-analytics-track'),
]
