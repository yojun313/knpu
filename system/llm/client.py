import logging
import re
from dataclasses import dataclass, field

from openai import AsyncOpenAI, OpenAI

from .config import LLMSettings, get_settings
from .errors import LLMError

logger = logging.getLogger(__name__)

Message = dict[str, str]


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


def _first_model_id(models) -> str:
    items = getattr(models, "data", models) or []
    if not items:
        raise LLMError("LLM 서버에 사용 가능한 모델이 없습니다.")
    first = items[0]
    model_id = (
        first.get("id") if isinstance(first, dict) else getattr(first, "id", first)
    )
    if not isinstance(model_id, str) or not model_id.strip():
        raise LLMError("LLM 서버의 모델 목록에 유효한 모델 ID가 없습니다.")
    return model_id


def clear_model_cache() -> None:
    """기존 호출 코드 호환용. 모델 목록은 캐시하지 않고 매 요청마다 조회한다."""


# OpenAI의 추론 모델(gpt-5, o1/o3/o4 …)은 max_tokens 대신 max_completion_tokens 를 받고,
# temperature 는 기본값만 허용한다.
_OPENAI_REASONING_RE = re.compile(r"^(gpt-5|o\d)", re.I)


def _is_openai_reasoning(base_url: str | None, model: str | None) -> bool:
    return bool(
        base_url
        and "api.openai.com" in base_url
        and model
        and _OPENAI_REASONING_RE.match(model)
    )


def _payload(messages, model, temperature, max_tokens, extra, base_url=None):
    payload = {"model": model, "messages": messages}
    reasoning = _is_openai_reasoning(base_url, model)
    # None은 보내지 않는다. 일부 서버(및 일부 모델)는 명시적 null을 거부한다.
    if temperature is not None and not reasoning:
        payload["temperature"] = temperature
    if max_tokens is not None:
        payload["max_completion_tokens" if reasoning else "max_tokens"] = max_tokens
    payload.update(extra or {})
    return payload


def _adapt_payload(payload: dict, err: Exception) -> dict | None:
    """서버가 파라미터를 거부한 400 오류면 그 파라미터를 고친 새 payload를, 아니면 None.

    모델마다 지원하는 파라미터가 달라서(예: max_tokens → max_completion_tokens,
    temperature 고정) 오류 메시지를 보고 한 번 맞춰서 다시 보낸다.
    """
    if getattr(err, "status_code", None) != 400:
        return None
    msg = str(err)
    new = dict(payload)
    if "max_tokens" in new and "max_completion_tokens" in msg:
        new["max_completion_tokens"] = new.pop("max_tokens")
    elif "temperature" in new and "temperature" in msg:
        new.pop("temperature")
    elif "response_format" in new and "response_format" in msg:
        new.pop("response_format")
    else:
        return None
    return new


_MAX_TOKEN_CAP = 32768


def _token_key(payload: dict) -> str | None:
    return next(
        (k for k in ("max_tokens", "max_completion_tokens") if k in payload), None
    )


def _cut_by_length(response) -> bool:
    """추론 모델이 생각하느라 출력 한도를 다 써서 본문이 빈 응답인지."""
    try:
        choice = response.choices[0]
        return (
            choice.finish_reason == "length"
            and not (choice.message.content or "").strip()
        )
    except (AttributeError, IndexError):
        return False


def _grow_tokens(payload: dict) -> dict | None:
    key = _token_key(payload)
    if not key or payload[key] >= _MAX_TOKEN_CAP:
        return None
    new = dict(payload)
    new[key] = min(payload[key] * 2, _MAX_TOKEN_CAP)
    return new


def _create(client, payload, **kw):
    grown = False
    for _ in range(4):
        try:
            response = client.chat.completions.create(**payload, **kw)
        except Exception as e:
            adapted = _adapt_payload(payload, e)
            if adapted is None:
                raise
            logger.info("LLM 파라미터 조정 후 재시도: %s", e)
            payload = adapted
            continue
        bigger = (
            None
            if grown or kw.get("stream")
            else (_cut_by_length(response) and _grow_tokens(payload))
        )
        if not bigger:
            return response
        logger.info(
            "출력 한도 초과로 빈 응답 — 한도를 %s로 늘려 재시도",
            bigger[_token_key(bigger)],
        )
        payload, grown = bigger, True
    return client.chat.completions.create(**payload, **kw)


async def _acreate(client, payload, **kw):
    grown = False
    for _ in range(4):
        try:
            response = await client.chat.completions.create(**payload, **kw)
        except Exception as e:
            adapted = _adapt_payload(payload, e)
            if adapted is None:
                raise
            logger.info("LLM 파라미터 조정 후 재시도: %s", e)
            payload = adapted
            continue
        bigger = (
            None
            if grown or kw.get("stream")
            else (_cut_by_length(response) and _grow_tokens(payload))
        )
        if not bigger:
            return response
        logger.info(
            "출력 한도 초과로 빈 응답 — 한도를 %s로 늘려 재시도",
            bigger[_token_key(bigger)],
        )
        payload, grown = bigger, True
    return await client.chat.completions.create(**payload, **kw)


def _extract_text(response) -> str:
    try:
        choice = response.choices[0]
        content = choice.message.content
    except (AttributeError, IndexError, KeyError) as e:
        raise LLMError(f"LLM 응답 형식을 해석할 수 없습니다: {e}") from e
    if not content or not content.strip():
        if getattr(choice, "finish_reason", None) == "length":
            # 추론 모델이 생각하느라 출력 한도를 다 쓰고 본문을 못 쓴 경우가 대부분이다
            raise LLMError(
                "LLM이 출력 한도(max_tokens) 안에 답을 끝내지 못해 빈 응답을 반환했습니다. "
                "추론 모델이라면 max_tokens를 늘려 주세요."
            )
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
            resolved = target.model or _first_model_id(client.models.list())
            response = _create(
                client,
                _payload(
                    full_messages,
                    resolved,
                    temperature,
                    max_tokens,
                    extra_body,
                    target.base_url,
                ),
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
            logger.warning(
                "LLM %s 호출 실패 (%s): %s", target.label, target.base_url, e
            )

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
            resolved = target.model or _first_model_id(await client.models.list())

            response = await _acreate(
                client,
                _payload(
                    full_messages,
                    resolved,
                    temperature,
                    max_tokens,
                    extra_body,
                    target.base_url,
                ),
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
            logger.warning(
                "LLM %s 호출 실패 (%s): %s", target.label, target.base_url, e
            )

    raise LLMError("LLM 호출에 실패했습니다.", attempts)


async def astream(
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
):
    """응답을 조각(str) 단위로 흘려보내는 async 제너레이터. 실패하면 LLMError.

    첫 조각이 나오기 전에 실패하면 다음 엔드포인트(폴백)로 넘어간다. 이미 조각을
    내보낸 뒤 끊기면 이어 붙일 수 없으므로 그대로 LLMError를 올린다.
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
        client = get_async_client(target.base_url, target.api_key)
        started = False
        try:
            resolved = target.model or _first_model_id(await client.models.list())

            payload = _payload(
                full_messages,
                resolved,
                temperature,
                max_tokens,
                extra_body,
                target.base_url,
            )
            for attempt in range(2):
                stream = await _acreate(client, payload, stream=True)
                finish = None
                async for chunk in stream:
                    if not chunk.choices:
                        continue
                    finish = chunk.choices[0].finish_reason or finish
                    delta = getattr(chunk.choices[0].delta, "content", None)
                    if delta:
                        started = True
                        yield delta
                if started:
                    return
                bigger = (
                    _grow_tokens(payload)
                    if finish == "length" and attempt == 0
                    else None
                )
                if not bigger:
                    break
                logger.info("스트림이 출력 한도로 비어 끝남 — 한도를 늘려 재시도")
                payload = bigger
            raise LLMError(
                "LLM이 출력 한도(max_tokens) 안에 답을 끝내지 못해 빈 응답을 반환했습니다."
                if finish == "length"
                else "LLM이 빈 응답을 반환했습니다."
            )
        except Exception as e:
            if started:
                raise LLMError(
                    "LLM 스트리밍이 중간에 끊겼습니다.", [(target.label, e)]
                ) from e
            attempts.append((f"{target.label} {target.base_url}", e))
            logger.warning(
                "LLM %s 스트리밍 실패 (%s): %s", target.label, target.base_url, e
            )

    raise LLMError("LLM 호출에 실패했습니다.", attempts)


def complete(prompt: str, **kwargs) -> str:
    """가장 간단한 형태 — 프롬프트를 넣고 문자열을 받는다."""
    return chat(prompt=prompt, **kwargs).text


async def acomplete(prompt: str, **kwargs) -> str:
    result = await achat(prompt=prompt, **kwargs)
    return result.text
