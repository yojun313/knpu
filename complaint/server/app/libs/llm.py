from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")


def _create_local_client():
    return OpenAI(api_key="dummy-key", base_url="http://localhost:9001/v1")


def _create_official_client():
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set for official OpenAI fallback")
    return OpenAI(api_key=api_key)


def llm_generate(query):
    try:
        client = _create_local_client()
        models = client.models.list()
        model_objs = getattr(models, "data", models) or []
        if not model_objs:
            raise RuntimeError("No models available from local server")
        first = model_objs[0]
        model_id = getattr(first, "id", first)

        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query},
            ]
        )

        model_id = model_id.replace('/models/', '').replace('__', '/')
        return response.choices[0].message.content, model_id
    except Exception:
        # 로컬 실패 시 공식 OpenAI로 폴백
        client = _create_official_client()
        response = client.chat.completions.create(
            model="gpt-5-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": query},
            ]
        )
        return response.choices[0].message.content, "gpt-5-mini"