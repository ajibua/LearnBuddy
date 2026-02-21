from django.db import models

class StudyMaterial(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='study_materials', null=True, blank=True)
    file = models.FileField(upload_to='materials/')
    file_type = models.CharField(max_length=20) # pdf, mp4, etc.
    summary = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-uploaded_at']
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"{self.file.name} - {user_str}"

# models.py

class ChatSession(models.Model):
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    study_material = models.ForeignKey(StudyMaterial, on_delete=models.CASCADE, related_name='chat_sessions', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        user_str = self.user.username if self.user else "Anonymous"
        return f"Session {self.id} - {user_str} - {self.created_at}"


class ChatMessage(models.Model):
    session = models.ForeignKey(ChatSession, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    role = models.CharField(max_length=10)  # 'user' or 'model'
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.role}: {self.content[:50]}"