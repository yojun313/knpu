"""사용자별 LLM 설정 — 로컬 LLM / 로컬 실패 시 내 GPT API / 항상 내 GPT API.

설정과 사용량은 systems DB에 사용자(uid)별로 저장되어 모든 KNPU 사이트에서 같다.
API 키는 서버 비밀값으로 암호화해 저장하고, 브라우저에는 끝 4자리만 돌려준다.

    from system.llm import user_llm
    for target in user_llm.plan(uid):          # 시도할 순서대로
        res = await achat(messages, **target.kwargs, max_tokens=...)
        user_llm.record_usage(uid, target, res)  # 내 API 키였다면 사용액을 기록

사용액은 응답의 토큰 수 × 아래 요금표로 계산한 '추정치'다. 실제 청구액은 OpenAI 대시보드가 기준이다.
"""

import base64
import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from openai import OpenAI

from .config import get_settings

logger = logging.getLogger(__name__)

MODES = {
    "local": "로컬 LLM만 사용",
    "local_then_openai": "로컬 LLM 우선, 실패하면 내 GPT API",
    "openai": "항상 내 GPT API",
}
DEFAULT_MODE = "local"
DEFAULT_LIMIT_USD = 5.0
OPENAI_BASE_URL = os.getenv(
    "LLM_USER_OPENAI_BASE_URL", "https://api.openai.com/v1"
).rstrip("/")

# 100만 토큰당 USD (입력, 출력). OpenAI 공개 요금 기준 추정치 — LLM_PRICE_OVERRIDES(JSON)로 덮어쓸 수 있다.
PRICES = {
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5": (1.25, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
}
try:
    PRICES.update(
        {
            k: tuple(v)
            for k, v in json.loads(os.getenv("LLM_PRICE_OVERRIDES") or "{}").items()
        }
    )
except (ValueError, TypeError):
    logger.warning("LLM_PRICE_OVERRIDES 형식이 올바르지 않아 무시합니다")
DEFAULT_MODEL = "gpt-5-mini"


class SettingsError(ValueError):
    """사용자에게 그대로 보여 줄 수 있는 설정 오류."""


# ── 저장소 ─────────────────────────────────────────────────────────────────
def _collections():
    from system.db import systems_db  # 지연 import: DB 없이도 모듈을 불러올 수 있게

    return systems_db["llm_user_settings"], systems_db["llm_user_usage"]


def _fernet():
    from cryptography.fernet import Fernet

    secret = os.getenv("LLM_KEY_SECRET") or os.getenv("JWT_SECRET")
    if not secret:
        raise SettingsError(
            "서버에 암호화 비밀값(LLM_KEY_SECRET)이 없어 API 키를 저장할 수 없습니다. 관리자에게 문의하세요."
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


def _month() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _load(uid: str) -> dict:
    col, _ = _collections()
    return col.find_one({"_id": uid}) or {}


def _usage(uid: str) -> dict:
    _, usage = _collections()
    return usage.find_one({"_id": f"{uid}:{_month()}"}) or {}


# ── 공개 설정 ──────────────────────────────────────────────────────────────
def public_settings(uid: str) -> dict:
    doc = _load(uid)
    u = _usage(uid)
    limit = float(doc.get("monthly_limit_usd", DEFAULT_LIMIT_USD))
    spent = float(u.get("cost_usd", 0.0))
    return {
        "mode": doc.get("mode", DEFAULT_MODE),
        "model": doc.get("model", DEFAULT_MODEL),
        "monthly_limit_usd": limit,
        "has_key": bool(doc.get("api_key_enc")),
        "key_hint": doc.get("key_hint", ""),
        "usage": {
            "month": _month(),
            "cost_usd": round(spent, 4),
            "calls": int(u.get("calls", 0)),
            "input_tokens": int(u.get("input_tokens", 0)),
            "output_tokens": int(u.get("output_tokens", 0)),
            "remaining_usd": round(max(0.0, limit - spent), 4),
            "recent": list(reversed(u.get("recent", [])))[:10],
        },
        "modes": MODES,
        "models": [
            {"id": m, "input_per_1m": p[0], "output_per_1m": p[1]}
            for m, p in PRICES.items()
        ],
        "local_model": "서버 모델 자동 선택",
    }


def _check_key(api_key: str) -> None:
    try:
        OpenAI(
            base_url=OPENAI_BASE_URL, api_key=api_key, timeout=15, max_retries=0
        ).models.list()
    except Exception as e:
        status = getattr(e, "status_code", None)
        if status == 401:
            raise SettingsError(
                "OpenAI가 이 API 키를 거부했습니다. 키를 다시 확인해 주세요."
            )
        raise SettingsError(f"API 키를 확인하지 못했습니다: {e}")


def save_settings(uid: str, body: dict) -> dict:
    mode = body.get("mode", DEFAULT_MODE)
    if mode not in MODES:
        raise SettingsError("사용 방식이 올바르지 않습니다.")
    model = body.get("model") or DEFAULT_MODEL
    if model not in PRICES:
        raise SettingsError("지원하지 않는 모델입니다.")
    try:
        limit = float(body.get("monthly_limit_usd", DEFAULT_LIMIT_USD))
    except (TypeError, ValueError):
        raise SettingsError("월 사용 한도는 숫자로 입력해 주세요.")
    if not 0 <= limit <= 1000:
        raise SettingsError("월 사용 한도는 0~1000 달러 사이로 입력해 주세요.")

    update = {
        "mode": mode,
        "model": model,
        "monthly_limit_usd": limit,
        "updated_at": datetime.now(timezone.utc),
    }
    unset = {}
    new_key = (body.get("api_key") or "").strip()
    if body.get("clear_key"):
        unset = {"api_key_enc": "", "key_hint": ""}
    elif new_key:
        if not new_key.startswith("sk-") or len(new_key) < 20:
            raise SettingsError("OpenAI API 키 형식(sk-로 시작)이 아닙니다.")
        _check_key(new_key)
        update["api_key_enc"] = _encrypt(new_key)
        update["key_hint"] = new_key[-4:]

    has_key = (bool(new_key) or bool(_load(uid).get("api_key_enc"))) and not body.get(
        "clear_key"
    )
    if mode != "local" and not has_key:
        raise SettingsError("GPT API를 쓰려면 API 키를 입력해 주세요.")

    col, _ = _collections()
    op = {"$set": update}
    if unset:
        op["$unset"] = unset
    col.update_one({"_id": uid}, op, upsert=True)
    return public_settings(uid)


# ── 호출 계획 · 사용량 ──────────────────────────────────────────────────────
@dataclass
class Target:
    provider: str  # local | openai
    label: str  # 화면·로그용 이름
    kwargs: dict = field(
        default_factory=dict
    )  # achat/chat 에 넘길 base_url/api_key/model
    model: str | None = None


def estimate_call_cost(
    model: str | None, messages: list[dict] | None, max_tokens: int | None
) -> float:
    """호출 전 대략적인 비용. 한글은 글자당 약 1토큰으로 넉넉히 잡고, 출력은 한도(최대 4000)로 본다."""
    chars = sum(len(str(m.get("content") or "")) for m in (messages or []))
    return estimate_cost(model, chars, min(max_tokens or 2000, 4000))


def plan(
    uid: str | None, messages: list[dict] | None = None, max_tokens: int | None = None
) -> tuple[list[Target], str | None]:
    """시도할 대상 목록과(있다면) 내 API를 못 쓰는 이유.

    messages·max_tokens 를 주면 이번 호출의 예상 비용까지 남은 한도 안에 드는지 본다.
    """
    local_default = Target("local", "로컬 LLM")
    if not uid:
        return [local_default], None
    try:
        doc = _load(uid)
    except Exception as e:  # DB 문제로 사용자 설정을 못 읽어도 로컬로는 동작한다
        logger.warning("사용자 LLM 설정을 읽지 못했습니다: %s", e)
        return [local_default], None
    mode = doc.get("mode", DEFAULT_MODE)
    if mode == "local":
        return [local_default], None

    note = None
    openai_target = None
    key = _decrypt(doc["api_key_enc"]) if doc.get("api_key_enc") else None
    if not key:
        note = "저장된 GPT API 키가 없거나 읽을 수 없습니다."
    else:
        limit = float(doc.get("monthly_limit_usd", DEFAULT_LIMIT_USD))
        spent = float(_usage(uid).get("cost_usd", 0.0))
        model = doc.get("model", DEFAULT_MODEL)
        need = estimate_call_cost(model, messages, max_tokens) if messages else 0.0
        if spent >= limit:
            note = f"이번 달 GPT API 사용 한도(${limit:.2f})에 도달해 내 API를 쓰지 않았습니다."
        elif spent + need > limit:
            note = (
                f"이번 호출 예상 비용(약 ${need:.4f})이 남은 한도(${limit - spent:.4f})를 넘어 "
                "내 API를 쓰지 않았습니다. 설정에서 월 한도를 올릴 수 있어요."
            )
        else:
            openai_target = Target(
                "openai",
                f"{model} (내 API 키)",
                {"base_url": OPENAI_BASE_URL, "api_key": key, "model": model},
                model,
            )

    if mode == "openai":
        return ([openai_target] if openai_target else []), note
    # 로컬 우선: 서버 공용 폴백 대신 사용자 키로 넘어가도록 로컬 주 엔드포인트만 명시한다
    s = get_settings()
    local_only = Target(
        "local",
        "로컬 LLM",
        {
            "base_url": s.base_url,
            "api_key": s.api_key or "not-needed",
            "model": s.model,
        },
    )
    return [local_only] + ([openai_target] if openai_target else []), note


def estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> float:
    p = PRICES.get(model or "", PRICES[DEFAULT_MODEL])
    return input_tokens / 1e6 * p[0] + output_tokens / 1e6 * p[1]


def record_usage(uid: str | None, target: Target, result, purpose: str = "") -> float:
    """내 API 키로 호출했으면 사용량을 기록하고 추정 비용(USD)을 돌려준다."""
    if not uid or target.provider != "openai":
        return 0.0
    usage = getattr(getattr(result, "raw", None), "usage", None)
    it = int(getattr(usage, "prompt_tokens", 0) or 0)
    ot = int(getattr(usage, "completion_tokens", 0) or 0)
    cost = estimate_cost(target.model, it, ot)
    try:
        _, col = _collections()
        col.update_one(
            {"_id": f"{uid}:{_month()}"},
            {
                "$inc": {
                    "cost_usd": cost,
                    "calls": 1,
                    "input_tokens": it,
                    "output_tokens": ot,
                },
                "$push": {
                    "recent": {
                        "$each": [
                            {
                                "at": datetime.now(timezone.utc).isoformat(
                                    timespec="seconds"
                                ),
                                "model": target.model,
                                "purpose": purpose[:40],
                                "input_tokens": it,
                                "output_tokens": ot,
                                "cost_usd": round(cost, 5),
                            }
                        ],
                        "$slice": -30,
                    }
                },
            },
            upsert=True,
        )
    except Exception as e:
        logger.error("GPT API 사용량 기록 실패: %s", e)
    return cost


# ── 계획대로 호출하는 도우미 ────────────────────────────────────────────────
@dataclass
class UserCall:
    result: object  # LLMResult
    target: Target
    cost_usd: float
    value: object = None  # validate 가 돌려준 값(예: 파싱한 JSON)
    notes: list = field(default_factory=list)  # 앞선 대상의 실패 사유 등


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
