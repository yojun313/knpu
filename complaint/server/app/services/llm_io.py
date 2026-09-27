"""system.llm 위의 얇은 계층 — JSON 응답을 안정적으로 받고, 스트림을 정리한다.

로컬 모델은 JSON 앞뒤에 설명·코드펜스·<think> 블록을 붙이거나 쉼표를 하나 더
찍는 일이 잦다. 여기서 한 번 걸러내고, 그래도 안 되면 "JSON만 다시" 요청을
한 번 더 보낸다. 호출부는 dict 아니면 LLMError 만 받는다.
"""

import json
import logging
import os
import re

from system.llm import LLMError, achat, astream

logger = logging.getLogger(__name__)

# vLLM/OpenAI는 response_format=json_object 로 문법 수준에서 JSON을 강제할 수 있다.
# 지원하지 않는 서버를 위해 끌 수 있게 둔다.
_JSON_MODE = os.getenv("COMPLAINT_LLM_JSON_MODE", "1") != "0"

_THINK_RE = re.compile(r"<think>.*?</think>", re.S)


def strip_think(text: str) -> str:
    text = _THINK_RE.sub("", text or "")
    # 닫는 태그만 남은 경우(서버가 여는 태그를 잘라낸 경우)
    if "</think>" in text:
        text = text.split("</think>", 1)[1]
    return text.strip()


def _balanced_object(text: str) -> str | None:
    """첫 '{'부터 짝이 맞는 '}'까지. 문자열 안의 괄호는 무시한다."""
    start = text.find("{")
    while start != -1:
        depth, in_str, esc = 0, False, False
        for i in range(start, len(text)):
            ch = text[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        start = text.find("{", start + 1)
    return None


def parse_json_object(text: str) -> dict:
    text = strip_think(text)
    text = re.sub(r"```(?:json)?", "", text, flags=re.I)
    candidates = []
    obj = _balanced_object(text)
    if obj:
        candidates.append(obj)
    candidates.append(text)
    for cand in candidates:
        for fixer in (lambda s: s, _loosen):
            try:
                value = json.loads(fixer(cand))
                if isinstance(value, dict):
                    return value
            except (json.JSONDecodeError, TypeError):
                continue
    raise ValueError("JSON 객체를 찾을 수 없습니다")


def _loosen(s: str) -> str:
    s = re.sub(r",\s*([}\]])", r"\1", s)  # 끝 쉼표
    s = s.replace("“", '"').replace("”", '"')  # 둥근 따옴표
    s = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", s)  # 제어문자
    # 문자열 안의 실제 줄바꿈 → \n
    out, in_str, esc = [], False, False
    for ch in s:
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            elif ch == "\n":
                out.append("\\n")
                continue
        elif ch == '"':
            in_str = True
        out.append(ch)
    return "".join(out)


async def chat_json(
    messages: list[dict], *, temperature: float = 0.2, max_tokens: int = 2048
) -> dict:
    """JSON 객체를 돌려주는 LLM 호출. 파싱 실패 시 한 번 복구를 시도한다."""
    extra = {"response_format": {"type": "json_object"}} if _JSON_MODE else None
    try:
        res = await achat(
            messages, temperature=temperature, max_tokens=max_tokens, extra_body=extra
        )
    except LLMError:
        if not extra:
            raise
        # response_format 을 모르는 서버일 수 있다 — 빼고 한 번 더
        res = await achat(messages, temperature=temperature, max_tokens=max_tokens)
    try:
        return parse_json_object(res.text)
    except ValueError:
        logger.warning("JSON 파싱 실패, 복구 요청: %s", res.text[:300])
    repair = messages + [
        {"role": "assistant", "content": res.text[:6000]},
        {
            "role": "user",
            "content": "위 응답을 설명 없이 올바른 JSON 객체 하나로만 다시 출력하세요. 코드블록도 쓰지 마세요.",
        },
    ]
    res2 = await achat(repair, temperature=0, max_tokens=max_tokens)
    try:
        return parse_json_object(res2.text)
    except ValueError as e:
        raise LLMError(
            f"LLM 응답을 JSON으로 해석하지 못했습니다: {res2.text[:200]}"
        ) from e


async def stream_text(
    messages: list[dict], *, temperature: float = 0.4, max_tokens: int = 1024
):
    """<think> 블록을 걸러낸 텍스트 조각을 흘려보낸다."""
    buf = ""
    thinking = None  # None: 아직 모름, True: <think> 안, False: 본문
    async for piece in astream(
        messages, temperature=temperature, max_tokens=max_tokens
    ):
        if thinking is False:
            yield piece
            continue
        buf += piece
        stripped = buf.lstrip()
        if thinking is None:
            if stripped.startswith("<think>"):
                thinking = True
            elif len(stripped) >= 7 or (
                stripped and not "<think>".startswith(stripped)
            ):
                thinking = False
                yield buf
                buf = ""
                continue
            else:
                continue
        if thinking and "</think>" in buf:
            thinking = False
            rest = buf.split("</think>", 1)[1].lstrip()
            buf = ""
            if rest:
                yield rest
    if thinking is None and buf.strip():
        yield buf
