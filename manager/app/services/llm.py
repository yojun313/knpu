import traceback
import requests
from openai import OpenAI

from core.setting import get_setting

def generateLLM(query, model):
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

    else:
        # 서버 URL
        url = "http://121.152.225.232:3333/api/process"

        # 전송할 데이터
        data = {
            "model_name": model,
            "question": query
        }

        try:
            # POST 요청 보내기
            response = requests.post(url, json=data)

            # 응답 확인
            if response.status_code == 200:
                result = response.json()['result']
                result = result.replace(
                    '<think>', '').replace('</think>', '')
                return result
            else:
                return f"Failed to get a valid response: {response.status_code} {response.text}"

        except requests.exceptions.RequestException as e:
            return f"Error communicating with the server: {e}"
