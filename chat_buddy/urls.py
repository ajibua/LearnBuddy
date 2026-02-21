from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing_view, name='landing'),
    path('auth/login/', views.login_view, name='login'),
    path('auth/signup/', views.signup_view, name='signup'),
    path('auth/logout/', views.logout_view, name='logout'),
    path('chat/', views.chat_view, name='chat'),
    path('api/process-pdf/', views.PDFUploadView.as_view(), name='process-pdf'),
    path('api/process-image/', views.ImageUploadView.as_view(), name='process-image'),
    path('api/chat/', views.chat_api, name='chat-api'),
    path('api/upload/', views.FileUploadView.as_view(), name='upload-file'),
    path('api/chat-history/', views.get_chat_history, name='chat-history'),
]
