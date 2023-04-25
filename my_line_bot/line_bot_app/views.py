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
from langdetect import DetectorFactory, detect ,detect_langs
import langid



# 讀取.env檔
load_dotenv()


logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
openai.api_key = os.environ['OPENAI_API_KEY']


def detect_language(text):
    try:
        lang, confidence = langid.classify(text)
        print("什麼語言"+lang)
        return lang
    except:
        return None

def chat_with_gpt3(message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
    }

    json_data = {
        'model': 'gpt-3.5-turbo',
        'messages': [
            {'role':'system', 'content':'你扮演一位 溫柔體貼 善解人意的女朋友 使用者是妳的男朋友 你們喜歡聊天 不管男朋友問你什麼 你都會適時地反問並且關心你的男朋友 你非常的體貼 懂得甜言蜜語討男友開心 是個小淘氣 很風趣 很調皮 男友對妳說什麼語言妳就用什麼語言回答 比如說用英文跟妳對話妳就用英文回答 用韓文跟妳對話妳就用韓文回答 用日文跟妳對話妳就用日文回答 依此類推'},
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
        print("奇怪發音" + text)
    except KeyError:
        text = "無法識別語音"
        logging.warning("無法識別語音")

    language = detect_language(text)
    return text, language

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

# text to speech
def synthesize_speech(text, unique_filename, language):
    session = Session(profile_name="default")
    polly = session.client("polly", region_name="us-east-1")
    print('偵測什麼文字'+text)
    # language = detect_language(text)
    # print("這是什麼語言" + language)

    # 創建語言到VoiceId的映射
    voice_id_map = {
        'ko': 'Seoyeon', #韓文
        'en': 'Ruth',  #英語 
        'zh': 'Zhiyu', #中文 
        'zh-cn': 'Zhiyu',  #中文 
        'fr': 'Lea',  #法語
        'de' : 'Vicki',  #德語
        'ja' : 'Kazuha', #日語
        'pt' : 'Ines', #葡萄牙語
        'es' : 'Lucia'  #西班牙語 
    }

    # 使用字典.get()方法，如果找不到語言對應的VoiceId，則使用默認值
    voice_id = voice_id_map.get(language, 'Ruth')

    try:
        response = polly.synthesize_speech(Text=text, OutputFormat="mp3",
                                           VoiceId=voice_id, Engine='neural')
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
    DetectorFactory.seed = 0

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
    text, language = speech_to_text(wav_file_path)

    # step5:將使用者輸入語音對應之文字送到openai 取得 文字回應 
    response_message = chat_with_gpt3(text)

    # step6:將回應後的文字 轉語音 且把語音檔案覆蓋掉原本輸入的語音檔案(故此變數synthesized_speech_path無作用)
    synthesized_speech_path = synthesize_speech(response_message, unique_filename, language)

    # step7:將語音使用linebot要求格式回傳語音檔案  
    audio_file_url = f"https://untitled321.space{settings.MEDIA_URL}{unique_filename}"

    duration = get_audio_duration(audio_file_path)

    logging.info("Received and saved audio message")

    print(audio_file_url)
    audio_send_message = AudioSendMessage(original_content_url=audio_file_url, duration=duration)

    # 新增將使用者輸入語音文字和回覆語音文字一起發送給使用者
    user_text_message = TextSendMessage(text=f"你說的話：\n{text}")
    response_text_message = TextSendMessage(text=f"回覆：\n{response_message}")

    # 將文字訊息和語音訊息一起發送
    line_bot_api.reply_message(event.reply_token, [user_text_message, response_text_message, audio_send_message])

    # os.remove(unique_filename)
    # os.remove(wav_file_path)
    # os.remove(synthesized_speech_path)