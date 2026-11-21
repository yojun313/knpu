"""서비스의 AI 호출 계획 — 모든 사용자(관리자 포함)가 연구실 전역 AI 모델을 쓴다.

예전에는 사용자가 본인 GPT API 키를 등록해 쓸 수 있었지만 지금은 지원하지 않는다. 어떤 모델을
어떤 순서로 쓸지는 관리자 대시보드의 '전역 AI 모델' 우선순위(system.llm.global_model)만 따른다.
호출부가 쓰던 plan / record_usage / achat_for_user 모양은 그대로 두어 기존 코드를 고치지 않아도 된다.

    from system.llm import user_llm
    call = await user_llm.achat_for_user(uid, messages, purpose="...", max_tokens=...)

이 모듈의 암호화 도우미(_encrypt/_decrypt)는 전역 설정에 추가한 API 키를 저장할 때도 쓴다.
"""

from system.llm_activity import tracked

import base64
import hashlib
import logging
import os
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

SERVER_LABEL = "연구실 서버 모델"


class SettingsError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 설정 오류."""


# ── 키 암호화(전역 AI 모델에 추가한 API 키 저장용) ─────────────────────────────
def _fernet():
    from cryptography.fernet import Fernet

    secret = os.getenv("LLM_KEY_SECRET") or os.getenv("JWT_SECRET")
    if not secret:
        raise SettingsError(
            "서버에 암호화 비밀값(LLM_KEY_SECRET)이 없어 API 키를 저장할 수 없습니다. 관리자에게 문의해 주시기 바랍니다."
        )
    key = base64.urlsafe_b64encode(
        hashlib.sha256(("knpu-llm-key:" + secret).encode()).digest()
    )
    return Fernet(key)


def _encrypt(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode()).decode()


def _decrypt(token: str) -> str | None:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:
        logger.error(
            "저장된 API 키를 복호화하지 못했습니다(서버 비밀값이 바뀌었을 수 있음)"
        )
        return None


# ── 화면용 정리 ─────────────────────────────────────────────────────────────
def public_model(target, model: str | None) -> str | None:
    """일반 사용자에게 보여 줄 모델 이름. 서버 모델 이름은 알리지 않는다."""
    return None


def public_llm(llm: dict | None) -> dict:
    """저장된 llm 정보(예전 결과 포함)를 일반 사용자 화면용으로 정리한다."""
    llm = dict(llm or {})
    if llm.get("provider") != "openai":  # 예전에 본인 GPT API로 만든 결과만 그대로 둔다
        llm.pop("model", None)
        if llm.get("used"):
            llm["used"] = SERVER_LABEL
    return llm


# ── 호출 계획 ───────────────────────────────────────────────────────────────
@dataclass
class Target:
    provider: str  # 항상 "local"(= 연구실 전역 AI 모델)
    label: str  # 화면·로그용 이름
    kwargs: dict = field(default_factory=dict)  # achat/chat 에 넘길 추가 인자(없음)
    model: str | None = None


def plan(
    uid: str | None = None,
    messages: list[dict] | None = None,
    max_tokens: int | None = None,
) -> tuple[list[Target], str | None]:
    """시도할 대상 목록. 누구에게나 전역 AI 모델 하나이며, 그 안의 우선순위·대체는 client 가 처리한다."""
    return [Target("local", SERVER_LABEL)], None


def record_usage(uid: str | None, target: Target, result, purpose: str = "") -> float:
    """개인 API 과금이 없으므로 기록할 비용도 없다(호출부 호환용)."""
    return 0.0


# ── 계획대로 호출하는 도우미 ────────────────────────────────────────────────
@dataclass
class UserCall:
    result: object  # LLMResult
    target: Target
    cost_usd: float
    value: object = None  # validate 가 돌려준 값(예: 파싱한 JSON)
    notes: list = field(default_factory=list)  # 앞선 대상의 실패 사유 등


@tracked("AI 분석 및 응답 생성", service=None)
async def achat_for_user(
    uid, messages, *, purpose="", validate=None, **kwargs
) -> UserCall:
    """사용자 설정 순서대로 호출한다. validate(text)가 예외를 내면 다음 대상으로 넘어간다."""
    from .client import achat
    from .errors import LLMError

    targets, note = plan(uid, messages, kwargs.get("max_tokens"))
    notes = [note] if note else []
    attempts = []
    for t in targets:
        try:
            res = await achat(messages, **t.kwargs, **kwargs)
        except LLMError as e:
            attempts.append((t.label, e))
            notes.append(f"{t.label} 실패: {e}")
            continue
        cost = record_usage(uid, t, res, purpose)
        try:
            value = validate(res.text) if validate else None
        except Exception as e:
            attempts.append((t.label, e))
            notes.append(f"{t.label}의 답을 해석하지 못함: {e}")
            continue
        return UserCall(res, t, cost, value, notes)
    if not targets:
        raise LLMError(note or "사용할 수 있는 LLM이 없습니다.")
    raise LLMError(
        "LLM 호출에 실패했습니다." + (f" ({note})" if note else ""), attempts
    )


@tracked("AI 분석 및 응답 생성", service=None)
def chat_for_user(uid, messages, *, purpose="", validate=None, **kwargs) -> UserCall:
    """achat_for_user 의 동기 버전."""
    from .client import chat
    from .errors import LLMError

    targets, note = plan(uid, messages, kwargs.get("max_tokens"))
    notes = [note] if note else []
    attempts = []
    for t in targets:
        try:
            res = chat(messages, **t.kwargs, **kwargs)
        except LLMError as e:
            attempts.append((t.label, e))
            notes.append(f"{t.label} 실패: {e}")
            continue
        cost = record_usage(uid, t, res, purpose)
        try:
            value = validate(res.text) if validate else None
        except Exception as e:
            attempts.append((t.label, e))
            notes.append(f"{t.label}의 답을 해석하지 못함: {e}")
            continue
        return UserCall(res, t, cost, value, notes)
    if not targets:
        raise LLMError(note or "사용할 수 있는 LLM이 없습니다.")
    raise LLMError(
        "LLM 호출에 실패했습니다." + (f" ({note})" if note else ""), attempts
    )
