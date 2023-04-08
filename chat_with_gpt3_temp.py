import requests
import json

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

# 使用範例
message = "Hello!"  # 可以修改這裡的訊息
response_message = chat_with_gpt3(message)
print(response_message)