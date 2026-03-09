import traceback
from openai import OpenAI
from services.api import *
from config import *
from core.setting import get_setting

def generateLLM(query, model='ChatGPT'):
    if model == 'ChatGPT':
        try:
            client = OpenAI(api_key=get_setting('GPT_Key'))
            model_name = "gpt-5-mini"

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ]
            )
            return response.choices[0].message.content

        except Exception:
            return (0, traceback.format_exc())

    elif model == 'Server LLM':
        try:
            # 1. 자체 Server LLM 시도
            model_resp = Request(
                method="get",
                url="/llm/v1/models",
                timeout=5,
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
            )
            
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content")

            if content is None or str(content).strip() == "":
                raise Exception("Server LLM returned empty content.")

            return content

        except Exception as e:
            print(f"Fallback triggered: {e}")
            try:
                proxy_payload = {
                    "model": "gpt-5-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": query},
                    ],
                }

                proxy_response = Request(
                    method="post",
                    url="/llm/v1/openai/chat/completions",
                    json=proxy_payload,
                )
                proxy_content = proxy_response.json()["choices"][0]["message"]["content"]
                
                if not proxy_content:
                    return (0, "Both Server LLM and OpenAI Proxy returned empty results.")
                    
                return proxy_content
            
            except Exception:
                return (0, traceback.format_exc())