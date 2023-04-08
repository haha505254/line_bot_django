from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, AudioMessage, AudioSendMessage
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
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from contextlib import closing
import sys
import subprocess
from tempfile import gettempdir
from pydub import AudioSegment
import requests
import json


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


OPENAI_API_KEY = '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'
line_bot_api = LineBotApi('ETKCbwm9fhQuQ2Tu3KjSo71tIc1jUdOF5Q3jdVWsN/EQ5G9x8gj2PPn8BZQc4Se7uwfVuzzQyqtYqRj+fZXFB/xMKDjKHpJUPko3w2+LoPNzcZxVEYooGacQR45+GJsUl4f8ZOy9GRLwFozzypH9VwdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('f48d4087c04e00b31b1b5264d1dcc2a5')

def chat_with_gpt3(message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + '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',
    }

    json_data = {
        'model': 'gpt-3.5-turbo',
        'messages': [
            {
                'role': 'user',
                'content': message,
            },
        ],
    }

    response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=json_data)
    response_json = json.loads(response.text)
    return response_json['choices'][0]['message']['content']



def convert_audio_to_wav(audio_file_path):
    audio = AudioSegment.from_file(audio_file_path, format="m4a")
    wav_file_path = audio_file_path.replace(".m4a", ".wav")
    audio.export(wav_file_path, format="wav")
    return wav_file_path

# Ensure static directory exists
if not os.path.exists(settings.STATIC_ROOT):
    os.makedirs(settings.STATIC_ROOT)

def speech_to_text(audio_file_path):
    recognizer = sr.Recognizer()

    with sr.AudioFile(audio_file_path) as audio_file:
        audio_data = recognizer.record(audio_file)

    try:
        text = recognizer.recognize_google(audio_data, language="en-US")
        print(text)
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
    return len(audio) + 1000

def synthesize_speech(text, unique_filename):
    
    session = Session(profile_name="default")
    polly = session.client("polly", region_name="us-east-1")

    try:
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId="Ruth", Engine='neural')
    except (BotoCoreError, ClientError) as error:
        print(error)
        sys.exit(-1)

    if "AudioStream" in response:
        with closing(response["AudioStream"]) as stream:
            audio_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
            try:
                with open(audio_file_path, "wb") as file:
                    file.write(stream.read())
            except IOError as error:
                print(error)
                sys.exit(-1)
    else:
        print("Could not stream audio")
        sys.exit(-1)

    return audio_file_path

@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):
    message_content = line_bot_api.get_message_content(event.message.id)
    unique_filename = f"{uuid.uuid4()}.m4a"

    audio_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(message_content.content)

    wav_file_path = convert_audio_to_wav(audio_file_path)
    text = speech_to_text(wav_file_path)
    response_message = chat_with_gpt3(text)
    synthesized_speech_path = synthesize_speech(response_message, unique_filename)

    audio_file_url = f"https://0196-123-194-216-207.jp.ngrok.io{settings.MEDIA_URL}{unique_filename}"

    duration = get_audio_duration(audio_file_path)

    logging.info("Received and saved audio message")

    print(audio_file_url)
    audio_send_message = AudioSendMessage(original_content_url=audio_file_url, duration=duration)
    line_bot_api.reply_message(event.reply_token, audio_send_message)

    # os.remove(unique_filename)
    # os.remove(wav_file_path)
    # os.remove(synthesized_speech_path)