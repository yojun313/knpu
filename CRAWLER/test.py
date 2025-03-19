# OpenAI 클라이언트 초기화
gpt_api_key = "***REMOVED***"
from openai import OpenAI

query = "hello"
client = OpenAI(api_key=gpt_api_key)

# 모델 이름 수정: gpt-4-turbo
model = "gpt-4-turbo"

# ChatGPT API 요청
response = client.chat.completions.create(
    model=model,
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": query},
    ]
)

# 응답 메시지 내용 추출
content = response.choices[0].message.content
print(content)