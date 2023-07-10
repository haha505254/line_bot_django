from django.db import models
from django.utils import timezone

class Message(models.Model):
    user_id = models.CharField(max_length=50)
    user_message = models.TextField()
    response_message = models.TextField()
    language = models.CharField(max_length=10)
    timestamp = models.DateTimeField(default=timezone.now)
    
    def __str__(self):
        return self.user_message[:50]