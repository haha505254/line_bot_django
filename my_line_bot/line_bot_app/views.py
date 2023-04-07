from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage,AudioMessage
import uuid
import os
import requests
import logging
import speech_recognition as sr
from pydub import AudioSegment
import io
import requests
import speech_recognition as sr


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

OPENAI_API_KEY = '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'
line_bot_api = LineBotApi('ETKCbwm9fhQuQ2Tu3KjSo71tIc1jUdOF5Q3jdVWsN/EQ5G9x8gj2PPn8BZQc4Se7uwfVuzzQyqtYqRj+fZXFB/xMKDjKHpJUPko3w2+LoPNzcZxVEYooGacQR45+GJsUl4f8ZOy9GRLwFozzypH9VwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f48d4087c04e00b31b1b5264d1dcc2a5')


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


@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    unique_filename = f"{uuid.uuid4()}.m4a"

    with open(unique_filename, 'wb') as audio_file:
        audio_file.write(message_content.content)

    logging.info("Received and saved audio message")

    # Convert m4a to wav
    m4a_audio = AudioSegment.from_file(unique_filename, "m4a")
    wav_filename = unique_filename.replace('.m4a', '.wav')
    m4a_audio.export(wav_filename, format="wav")

    text = speech_to_text(wav_filename)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=text))

    # Clean up the files
    # os.remove(unique_filename)
    # os.remove(wav_filename)