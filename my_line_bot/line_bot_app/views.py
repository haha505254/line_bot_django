import io
import json
import logging
import os
import subprocess
import sys
import uuid
from contextlib import closing
from tempfile import gettempdir

import langid
import openai
import requests
import speech_recognition as sr
from boto3 import Session
from botocore.exceptions import BotoCoreError, ClientError
from django.conf import settings
from django.core.files.storage import default_storage
from django.http import HttpResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from dotenv import load_dotenv
from langdetect import DetectorFactory, detect, detect_langs
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (AudioMessage, AudioSendMessage, MessageEvent,
                            TextMessage, TextSendMessage)
from pydub import AudioSegment

from .models import Message

# 讀取.env檔
load_dotenv()



#此設定只需做一次就好
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d\n')
logger = logging.getLogger(__name__)


line_bot_api = LineBotApi(os.environ['LINE_CHANNEL_ACCESS_TOKEN'])
handler = WebhookHandler(os.environ['LINE_CHANNEL_SECRET'])
openai.api_key = os.environ['OPENAI_API_KEY']


def detect_language(text):
    try:
        lang, confidence = langid.classify(text)
        logger.info("語言檢測: "+lang)
        return lang
    except:
        logging.error("Language detection failed")
        return None


def chat_with_gpt3(user_id, message):
    headers = {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + os.environ['OPENAI_API_KEY'],
    }


    # 先建立一個開始的system訊息
    messages = [
        {
            'role':'system',
            'content':'你扮演一位 溫柔體貼 善解人意的女朋友 使用者是妳的男朋友 你們喜歡聊天 不管男朋友問你什麼 你都會適時地反問並且關心你的男朋友 你非常的體貼 懂得甜言蜜語討男友開心 是個小淘氣 很風趣 很調皮 男友對妳說什麼語言妳就用什麼語言回答 比如說用英文跟妳對話妳就用英文回答 用韓文跟妳對話妳就用韓文回答 用日文跟妳對話妳就用日文回答 依此類推',
        },
    ]
    # 獲取這個用戶的所有歷史訊息
    history_messages = Message.objects.filter(user_id=user_id).order_by('-timestamp')[:5]
    history_messages = list(history_messages)
    history_messages.reverse()



    # 將所有的歷史訊息添加到messages列表中
    for msg in history_messages:
        messages.append({'role': 'user', 'content': msg.user_message})
        messages.append({'role': 'assistant', 'content': msg.response_message})
        # 添加當前的用戶訊息
    messages.append({'role': 'user', 'content': message})

    json_data = {
        'model': 'gpt-3.5-turbo',
        'messages': messages,
    }
    logger.info("GPT-3 API 請求內容：" + str(json_data))

    response = requests.post('https://api.openai.com/v1/chat/completions', headers=headers, json=json_data)
    response_json = json.loads(response.text)
    logging.info(f"Response from GPT-3: {response_json['choices'][0]['message']['content']}")
    return response_json['choices'][0]['message']['content']



def convert_audio_to_wav(audio_file_path):
    audio = AudioSegment.from_file(audio_file_path, format="m4a")
    wav_file_path = audio_file_path.replace(".m4a", ".wav")
    audio.export(wav_file_path, format="wav", parameters=["-q:a", "0", "-ac", "1", "-ar", "16000"])
    logging.info(f"Converted audio file to WAV: {wav_file_path}")
    return wav_file_path

# Ensure static directory exists
if not os.path.exists(settings.STATIC_ROOT):
    os.makedirs(settings.STATIC_ROOT)

def speech_to_text(audio_file_path):
    with open(audio_file_path, "rb") as audio_file:
        transcript = openai.Audio.transcribe("whisper-1", audio_file)

    try:
        text = transcript['text']
        logger.info("識別的語音內容：" + text)
    except KeyError:
        text = "無法識別語音"
        logger.info("無法識別語音")

    language = detect_language(text)
    logging.info(f"Transcribed speech: {text}")
    logging.info(f"Detected language: {language}")
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
    logging.info(f"Audio duration: {len(audio)}")
    return len(audio) + 1000

# text to speech
def synthesize_speech(text, unique_filename, language):
    session = Session(profile_name="default")
    polly = session.client("polly", region_name="us-east-1")
    logger.info('待合成的文字：'+text)
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
    logging.info(f"Synthesized speech for text: {text}")
    return audio_file_path



# 入口點
@handler.add(MessageEvent, message=AudioMessage)
def handle_audio_message(event):

    logging.info("Processing audio message...")

    DetectorFactory.seed = 0

    # step1:取得音檔訊息
    message_content = line_bot_api.get_message_content(event.message.id)

    # step2:將音檔保存到MEDIA_folder 方便等等讀取 檔名使用uuid4 避免重複
    unique_filename = f"{uuid.uuid4()}.wav"
    audio_file_path = os.path.join(settings.MEDIA_ROOT, unique_filename)
    with open(audio_file_path, 'wb') as audio_file:
        audio_file.write(message_content.content)

    # step3:將音檔從m4a轉為wav (因為語音辨識speech_recognition 只接受wav) 
    logging.info("Converting audio to WAV...")
    wav_file_path = convert_audio_to_wav(audio_file_path)
    logging.info("Converted audio to WAV")

    # step4:將音檔使用speech_recognition語音轉文字
    logging.info("Transcribing speech...")
    text, language = speech_to_text(wav_file_path)
    # 獲取用戶ID
    user_id = event.source.user_id
    # step5:將使用者輸入語音對應之文字送到openai 取得 文字回應 
    response_message = chat_with_gpt3(user_id, text)

    # step6:將回應後的文字 轉語音 且把語音檔案覆蓋掉原本輸入的語音檔案(故此變數synthesized_speech_path無作用)
    logging.info("Synthesizing speech...")
    synthesized_speech_path = synthesize_speech(response_message, unique_filename, language)
    logging.info("Synthesized speech")

    # step7:將語音使用linebot要求格式回傳語音檔案  
    SERVER_HOSTNAME = 'https://a22f-125-229-69-223.ngrok-free.app'
    audio_file_url = f"{SERVER_HOSTNAME}{settings.MEDIA_URL}{unique_filename}"

    duration = get_audio_duration(audio_file_path)

    logging.info("Received and saved audio message")

    logger.info("音檔 URL: "+audio_file_url)
    audio_send_message = AudioSendMessage(original_content_url=audio_file_url, duration=duration)

    # 新增將使用者輸入語音文字和回覆語音文字一起發送給使用者
    user_text_message = TextSendMessage(text=f"你說的話：\n{text}")
    response_text_message = TextSendMessage(text=f"回覆：\n{response_message}")

    # 將文字訊息和語音訊息一起發送
    line_bot_api.reply_message(event.reply_token, [user_text_message, response_text_message, audio_send_message])

    # 在handle_audio_message函數的相應部分添加以下代碼
    # 儲存這次的訊息和回覆
    message_instance = Message(
        user_id=user_id,
        user_message=text,
        response_message=response_message,
        language=language
    )
    message_instance.save()
    # os.remove(unique_filename)
    # os.remove(wav_file_path)
    # os.remove(synthesized_speech_path)