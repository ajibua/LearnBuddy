from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('chat/', views.chat_view, name='chat'),
    path('api/process-pdf/', views.PDFUploadView.as_view(), name='process-pdf'),
    path('api/process-image/', views.ImageUploadView.as_view(), name='process-image'),
    path('api/chat/', views.chat_api, name='chat-api'),
    path('api/upload-pdf/', views.PDFUploadSummarizeView.as_view(), name='upload-pdf'),
    path('api/chat-history/', views.get_chat_history, name='chat-history'),
]