import traceback
from openai import OpenAI
from services.api import *
from config import *


from core.setting import get_setting

def generateLLM(query, model = 'ChatGPT'):
    if model == 'ChatGPT':
        try:
            # OpenAI 클라이언트 초기화
            client = OpenAI(api_key=get_setting('GPT_Key'))

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

        except Exception as e:
            # 예외 발생 시 에러 메시지 반환
            return (0, traceback.format_exc())

    elif model == 'Server LLM':
        try:
            model_resp = Request(
                method="get",
                url="/llm/v1/models",
                timeout=10,
            )

            model_data = model_resp.json().get("data", [])
            if not model_data:
                raise Exception("No model available on Server LLM")

            model_id = model_data[0]["id"]

            payload = {
                "model": model_id,
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ],
                "temperature": 0.7,
                "max_tokens": 1024,
            }

            response = Request(
                method="post",
                url="/llm/v1/chat/completions",
                json=payload,
                timeout=60,
            )

            result = response.json()
            return result["choices"][0]["message"]["content"]

        except Exception:
            return (0, traceback.format_exc())


        
