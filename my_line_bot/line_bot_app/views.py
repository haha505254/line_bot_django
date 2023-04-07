from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage,AudioMessage,AudioSendMessage
import uuid
import os
import requests
import logging
import speech_recognition as sr
from pydub import AudioSegment
import io
import requests
import speech_recognition as sr
from django.conf import settings
import uuid
import os
import logging
from django.core.files.storage import default_storage

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

OPENAI_API_KEY = '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'
line_bot_api = LineBotApi('ETKCbwm9fhQuQ2Tu3KjSo71tIc1jUdOF5Q3jdVWsN/EQ5G9x8gj2PPn8BZQc4Se7uwfVuzzQyqtYqRj+fZXFB/xMKDjKHpJUPko3w2+LoPNzcZxVEYooGacQR45+GJsUl4f8ZOy9GRLwFozzypH9VwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f48d4087c04e00b31b1b5264d1dcc2a5')


# Ensure static directory exists
if not os.path.exists(settings.STATIC_ROOT):
    os.makedirs(settings.STATIC_ROOT)


def speech_to_text(audio_file_path):
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_file_path) as audio_file:
        audio_data = recognizer.record(audio_file)

    try:
        text = recognizer.recognize_google(audio_data, language="zh-TW")
    except sr.UnknownValueError:
        text = "無法識別語音"
        logging.warning("無法識別語音")
    except sr.RequestError as e:
        text = f"發生錯誤：{e}"
        logging.error(f"發生錯誤：{e}")
    return text


@csrf_exempt
def callback(request):
    signature = request.META['HTTP_X_LINE_SIGNATURE']
    body = request.body.decode('utf-8')

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logging.error("Invalid signature")
        return HttpResponseBadRequest()

    return HttpResponse()


def get_audio_duration(audio_file_path):
    audio = AudioSegment.from_file(audio_file_path)
    return len(audio)+1000


@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    # 在 handle_audio_message 函数中
    unique_filename = f"{uuid.uuid4()}.m4a"

    # 保存音频文件到 media 文件夹
    audio_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(message_content.content)

    # 获取音频文件的 URL
    audio_file_url = f"https://0196-123-194-216-207.jp.ngrok.io{settings.MEDIA_URL}{unique_filename}"

    duration = get_audio_duration(audio_file_path)

    logging.info("Received and saved audio message")

    print(audio_file_url)
    audio_send_message = AudioSendMessage(original_content_url=  audio_file_url, duration=duration )
    line_bot_api.reply_message(event.reply_token, audio_send_message)
    # Clean up the files
    # os.remove(unique_filename)
    # os.remove(wav_filename)