import traceback
from config import *
import requests

def get_api_headers():
    token = LLM_KEY
    return {"Authorization": f"Bearer {token}"}

def generateLLM(query):
    try:
        model_resp = requests.get(
            f"{LLM_API_URL}/llm/v1/models", headers=get_api_headers(), timeout=5
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

        response = requests.post(
            f"{LLM_API_URL}/llm/v1/chat/completions",
            headers=get_api_headers(),
            json=payload,
        )

        result = response.json()
        content = result.get("choices", [{}])[0].get("message", {}).get("content")

        if not content:
            raise Exception("Server LLM returned empty content.")

        return content

    except Exception:
        try:
            proxy_payload = {
                "model": "gpt-5-mini",
                "messages": [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": query},
                ],
            }
            
            proxy_response = requests.post(
                f"{LLM_API_URL}/llm/v1/openai/chat/completions",
                headers=get_api_headers(),
                json=proxy_payload,
            )

            proxy_result = proxy_response.json()
            return proxy_result["choices"][0]["message"]["content"]

        except Exception:
            return (0, traceback.format_exc())
