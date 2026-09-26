"""OpenAI 호환 LLM 클라이언트 — 전역 공용.

사용 예:

    from system.llm import complete
    text = complete("한 문장으로 요약해줘: ...")

    from system.llm import chat
    res = chat([{"role": "user", "content": "안녕"}])
    print(res.text, res.model)
"""

import logging
import threading
from dataclasses import dataclass, field

from openai import AsyncOpenAI, OpenAI

from .config import LLMSettings, get_settings
from .errors import LLMError

logger = logging.getLogger(__name__)

Message = dict[str, str]

# (base_url, api_key) -> 자동 탐색한 모델 id
_model_cache: dict[tuple[str | None, str | None], str] = {}
_model_lock = threading.Lock()


@dataclass
class LLMResult:
    text: str
    model: str
    base_url: str
    used_fallback: bool = False
    raw: object = field(default=None, repr=False)

    @property
    def display_model(self) -> str:
        """vLLM이 돌려주는 '/models/org__name' 형태를 사람이 읽을 수 있게 정리한다."""
        return self.model.replace("/models/", "").replace("__", "/")

    def __str__(self) -> str:
        return self.text


@dataclass
class _Target:
    """한 번의 시도 대상(주 엔드포인트 또는 폴백)."""

    label: str
    base_url: str
    api_key: str | None
    model: str | None
    is_fallback: bool = False


def _targets(settings: LLMSettings, model: str | None) -> list[_Target]:
    targets = [
        _Target(
            label="primary",
            base_url=settings.base_url,
            api_key=settings.api_key,
            model=model or settings.model,
        )
    ]
    if settings.has_fallback:
        targets.append(
            _Target(
                label="fallback",
                base_url=settings.fallback_base_url,
                api_key=settings.fallback_api_key,
                # 폴백은 주 모델 이름이 없을 수 있으므로 폴백 전용 모델을 쓴다.
                model=settings.fallback_model,
                is_fallback=True,
            )
        )
    return targets


def _build_messages(
    prompt: str | None,
    messages: list[Message] | None,
    system: str | None,
    settings: LLMSettings,
) -> list[Message]:
    if messages is not None:
        if prompt is not None:
            raise ValueError("prompt와 messages는 동시에 쓸 수 없습니다.")
        return list(messages)
    if prompt is None:
        raise ValueError("prompt 또는 messages 중 하나는 필요합니다.")
    return [
        {"role": "system", "content": system or settings.system_prompt},
        {"role": "user", "content": prompt},
    ]


def get_client(base_url: str | None = None, api_key: str | None = None) -> OpenAI:
    """설정된 엔드포인트를 가리키는 OpenAI SDK 클라이언트.

    스트리밍이나 임베딩처럼 이 모듈이 감싸지 않은 기능이 필요할 때 직접 쓴다.
    """
    settings = get_settings()
    return OpenAI(
        base_url=base_url or settings.base_url,
        # SDK는 키가 None이면 예외를 던진다. 인증이 없는 로컬 서버용 더미 값.
        api_key=api_key or settings.api_key or "not-needed",
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )


def get_async_client(
    base_url: str | None = None, api_key: str | None = None
) -> AsyncOpenAI:
    settings = get_settings()
    return AsyncOpenAI(
        base_url=base_url or settings.base_url,
        api_key=api_key or settings.api_key or "not-needed",
        timeout=settings.timeout,
        max_retries=settings.max_retries,
    )


def _cached_model(key, resolver):
    with _model_lock:
        if key in _model_cache:
            return _model_cache[key]
    model_id = resolver()
    with _model_lock:
        _model_cache[key] = model_id
    return model_id


def _first_model_id(models) -> str:
    items = getattr(models, "data", models) or []
    if not items:
        raise LLMError("LLM 서버에 사용 가능한 모델이 없습니다.")
    first = items[0]
    return getattr(first, "id", first)


def clear_model_cache() -> None:
    with _model_lock:
        _model_cache.clear()


def _payload(messages, model, temperature, max_tokens, extra):
    payload = {"model": model, "messages": messages}
    # None은 보내지 않는다. 일부 서버(및 일부 모델)는 명시적 null을 거부한다.
    if temperature is not None:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    payload.update(extra or {})
    return payload


def _extract_text(response) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError) as e:
        raise LLMError(f"LLM 응답 형식을 해석할 수 없습니다: {e}") from e
    if not content or not content.strip():
        raise LLMError("LLM이 빈 응답을 반환했습니다.")
    return content


def chat(
    messages: list[Message] | None = None,
    *,
    prompt: str | None = None,
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict | None = None,
) -> LLMResult:
    """LLM을 호출하고 LLMResult를 돌려준다. 실패하면 LLMError.

    base_url/api_key를 주면 전역 설정 대신 그 엔드포인트만 사용한다
    (예: 사용자 세션 토큰으로 manager 프록시를 호출할 때).
    """
    settings = get_settings()
    full_messages = _build_messages(prompt, messages, system, settings)

    if base_url or api_key:
        targets = [
            _Target(
                label="explicit",
                base_url=base_url or settings.base_url,
                api_key=api_key or settings.api_key,
                model=model or settings.model,
            )
        ]
    else:
        targets = _targets(settings, model)

    attempts: list[tuple[str, Exception]] = []
    for target in targets:
        client = get_client(target.base_url, target.api_key)
        try:
            resolved = target.model or _cached_model(
                (target.base_url, target.api_key),
                lambda: _first_model_id(client.models.list()),
            )
            response = client.chat.completions.create(
                **_payload(
                    full_messages, resolved, temperature, max_tokens, extra_body
                )
            )
            return LLMResult(
                text=_extract_text(response),
                model=getattr(response, "model", None) or resolved,
                base_url=target.base_url,
                used_fallback=target.is_fallback,
                raw=response,
            )
        except Exception as e:
            attempts.append((f"{target.label} {target.base_url}", e))
            logger.warning("LLM %s 호출 실패 (%s): %s", target.label, target.base_url, e)

    raise LLMError("LLM 호출에 실패했습니다.", attempts)


async def achat(
    messages: list[Message] | None = None,
    *,
    prompt: str | None = None,
    system: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
    extra_body: dict | None = None,
) -> LLMResult:
    """chat()의 async 버전."""
    settings = get_settings()
    full_messages = _build_messages(prompt, messages, system, settings)

    if base_url or api_key:
        targets = [
            _Target(
                label="explicit",
                base_url=base_url or settings.base_url,
                api_key=api_key or settings.api_key,
                model=model or settings.model,
            )
        ]
    else:
        targets = _targets(settings, model)

    attempts: list[tuple[str, Exception]] = []
    for target in targets:
        client = get_async_client(target.base_url, target.api_key)
        try:
            resolved = target.model
            if not resolved:
                key = (target.base_url, target.api_key)
                with _model_lock:
                    resolved = _model_cache.get(key)
                if not resolved:
                    resolved = _first_model_id(await client.models.list())
                    with _model_lock:
                        _model_cache[key] = resolved

            response = await client.chat.completions.create(
                **_payload(
                    full_messages, resolved, temperature, max_tokens, extra_body
                )
            )
            return LLMResult(
                text=_extract_text(response),
                model=getattr(response, "model", None) or resolved,
                base_url=target.base_url,
                used_fallback=target.is_fallback,
                raw=response,
            )
        except Exception as e:
            attempts.append((f"{target.label} {target.base_url}", e))
            logger.warning("LLM %s 호출 실패 (%s): %s", target.label, target.base_url, e)

    raise LLMError("LLM 호출에 실패했습니다.", attempts)


def complete(prompt: str, **kwargs) -> str:
    """가장 간단한 형태 — 프롬프트를 넣고 문자열을 받는다."""
    return chat(prompt=prompt, **kwargs).text


async def acomplete(prompt: str, **kwargs) -> str:
    result = await achat(prompt=prompt, **kwargs)
    return result.text
