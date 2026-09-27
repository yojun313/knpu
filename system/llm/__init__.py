"""전역 LLM 모듈.

.env에 OpenAI 호환 엔드포인트를 설정하면 프로젝트 어디서든 같은 방식으로 쓴다.

    from system.llm import complete
    text = complete("요약해줘: ...")

    from system.llm import chat, LLMError
    try:
        res = chat([{"role": "user", "content": "안녕"}], max_tokens=512)
        print(res.text, res.display_model)
    except LLMError as e:
        ...
"""

from .client import (
    LLMResult,
    Message,
    achat,
    acomplete,
    astream,
    chat,
    clear_model_cache,
    complete,
    get_async_client,
    get_client,
)
from .config import LLMSettings, get_settings, reload_settings
from .errors import LLMError

__all__ = [
    "LLMError",
    "LLMResult",
    "LLMSettings",
    "Message",
    "achat",
    "acomplete",
    "astream",
    "chat",
    "clear_model_cache",
    "complete",
    "get_async_client",
    "get_client",
    "get_settings",
    "reload_settings",
]
