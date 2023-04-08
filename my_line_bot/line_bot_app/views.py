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
from dotenv import load_dotenv
import openai
# 讀取.env檔
load_dotenv()


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
openai.api_key = os.environ['OPENAI_API_KEY']


def chat_with_gpt3(message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
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
    audio.export(wav_file_path, format="wav", parameters=["-q:a", "0", "-ac", "1", "-ar", "16000"])
    return wav_file_path

# Ensure static directory exists
if not os.path.exists(settings.STATIC_ROOT):
    os.makedirs(settings.STATIC_ROOT)

def speech_to_text(audio_file_path):
    with open(audio_file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

    try:
        text = transcript['text']
        print("奇怪發音"+text)
    except KeyError:
        text = "無法識別語音"
        logging.warning("無法識別語音")

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
    # Seoyeon kr   Ruth en
    try:
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId="Seoyeon", Engine='neural')
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



# 入口點 
@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):

    # step1:取得音檔訊息
    message_content = line_bot_api.get_message_content(event.message.id)
    

    # step2:將音檔保存到MEDIA_folder 方便等等讀取 檔名使用uuid4 避免重複
    unique_filename = f"{uuid.uuid4()}.wav"
    audio_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(message_content.content)

    # step3:將音檔從m4a轉為wav (因為語音辨識speech_recognition 只接受wav) 
    wav_file_path = convert_audio_to_wav(audio_file_path)

    # step4:將音檔使用speech_recognition語音轉文字
    text = speech_to_text(wav_file_path)

    # step5:將使用者輸入語音對應之文字送到openai 取得 文字回應 
    response_message = chat_with_gpt3(text)

    # step6:將回應後的文字 轉語音 且把語音檔案覆蓋掉原本輸入的語音檔案(故此變數synthesized_speech_path無作用)
    synthesized_speech_path = synthesize_speech(response_message, unique_filename)

    # step7:將語音使用linebot要求格式回傳語音檔案  
    audio_file_url = f"https://2a5a-1-200-48-236.ngrok-free.app{settings.MEDIA_URL}{unique_filename}"

    duration = get_audio_duration(audio_file_path)

    logging.info("Received and saved audio message")

    print(audio_file_url)
    audio_send_message = AudioSendMessage(original_content_url=audio_file_url, duration=duration)
    line_bot_api.reply_message(event.reply_token, audio_send_message)

    # os.remove(unique_filename)
    # os.remove(wav_file_path)
    # os.remove(synthesized_speech_path)