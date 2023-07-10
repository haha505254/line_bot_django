from django.contrib import admin
from .models import Message

class MessageAdmin(admin.ModelAdmin):
    list_display = ('user_id', 'user_message', 'response_message', 'language', 'timestamp')

admin.site.register(Message, MessageAdmin)