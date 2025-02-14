import googletrans
import asyncio
from openai import OpenAI

async def translate_text(inStr):
    translator = googletrans.Translator()
    outStr = await translator.translate(inStr, dest='en', src='auto')
    print(f"{inStr} => {outStr.text}")

asyncio.run(translate_text("바나나"))

import openai

def gpt_generate(query):
    gpt_api_key = "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"
    # OpenAI 클라이언트 초기화
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
    return content

