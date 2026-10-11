import traceback
import logging
import threading
from contextlib import contextmanager
from openai import OpenAI
from services.api import Request
from core.setting import get_setting


@contextmanager
def _personal_ai_activity():
    job_id = Request("post", "/llm-activity", timeout=10).json()["id"]
    stop = threading.Event()

    def report(status=None):
        try:
            Request(
                "patch",
                "/llm-activity/" + job_id,
                json={"status": status or "running"},
                timeout=10,
            )
        except Exception:
            logging.getLogger(__name__).warning(
                "AI 작업 상태를 서버에 보고하지 못했습니다."
            )

    def heartbeat():
        while not stop.wait(15):
            report()

    threading.Thread(target=heartbeat, daemon=True).start()
    try:
        yield
    except BaseException:
        report("error")
        raise
    else:
        report("done")
    finally:
        stop.set()


def generateLLM(query, model="ChatGPT"):
    if model == "ChatGPT":
        try:
            with _personal_ai_activity():
                client = OpenAI(api_key=get_setting("GPT_Key"))
                model_name = "gpt-5-mini"

                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": query},
                    ],
                )
                return response.choices[0].message.content

        except Exception:
            return (0, traceback.format_exc())

    elif model == "Server LLM":
        try:
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

                proxy_response = Request(
                    method="post",
                    url="/llm/v1/openai/chat/completions",
                    json=proxy_payload,
                )

                proxy_result = proxy_response.json()
                return proxy_result["choices"][0]["message"]["content"]

            except Exception:
                return (0, traceback.format_exc())
