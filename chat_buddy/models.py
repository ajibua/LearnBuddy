from django.db import models
from django.utils import timezone

class StudyMaterial(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='study_materials', null=True, blank=True)
    file = models.FileField(upload_to='materials/')
    file_type = models.CharField(max_length=20)
    summary = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{self.file.name} - {user_str}"

class ChatSession(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    title = models.CharField(max_length=120, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"Session {self.id} - {user_str} - {self.created_at}"

class ChatMessage(models.Model):
    FEEDBACK_CHOICES = [('up', 'up'), ('down', 'down')]

    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    role = models.CharField(max_length=10)
    content = models.TextField()
    feedback = models.CharField(max_length=4, choices=FEEDBACK_CHOICES, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"

class FlashcardDeck(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='flashcard_decks')
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.SET_NULL, related_name='flashcard_decks', null=True, blank=True)
    title = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Flashcard(models.Model):
    deck = models.ForeignKey(FlashcardDeck, on_delete=models.CASCADE, related_name='cards')
    front = models.TextField()
    back = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Card {self.id} in {self.deck.title}"

class Quiz(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='quizzes')
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.SET_NULL, related_name='quizzes', null=True, blank=True)
    title = models.CharField(max_length=120)
    score = models.IntegerField(null=True, blank=True)
    total_questions = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Quiz {self.title} - Score: {self.score}/{self.total_questions}"

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    option_a = models.CharField(max_length=255)
    option_b = models.CharField(max_length=255)
    option_c = models.CharField(max_length=255)
    option_d = models.CharField(max_length=255)
    correct_option = models.CharField(max_length=1)
    explanation = models.TextField()
    user_answer = models.CharField(max_length=1, null=True, blank=True)

    def __str__(self):
        return f"Question {self.id} in {self.quiz.title}"

class StudySessionRecord(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='study_sessions')
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.SET_NULL, related_name='study_sessions', null=True, blank=True)
    activity_type = models.CharField(max_length=20)
    duration_seconds = models.IntegerField(default=0)
    date = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.username} - {self.activity_type} - {self.duration_seconds}s on {self.date}"