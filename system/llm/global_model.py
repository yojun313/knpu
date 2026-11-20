"""전역 AI 모델 설정 — 관리자 대시보드에서 고르는 '서버 기본 모델'.

모든 서비스가 system.llm(chat/achat/astream)을 부를 때 이 설정을 따른다.
- local : .env 의 로컬 LLM(LLM_BASE_URL). 실패하면 .env 의 폴백 설정을 따른다(기존 동작).
- openai: .env 의 OPENAI_API_KEY 로 OpenAI 모델을 부른다. 실패하면 로컬 LLM으로 넘어간다.

설정은 systems DB의 admin_settings 컬렉션(_id = "llm_global")에 두고, 프로세스마다 짧게 캐시해
서비스를 재시작하지 않아도 몇 초 안에 반영된다. DB를 읽을 수 없으면 마지막 값(없으면 로컬)을 쓴다.
사용자가 '내 GPT API'를 직접 고른 호출(user_llm 의 명시 대상)은 이 설정과 무관하다.
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

PROVIDERS = {
    "local": "로컬 LLM (.env LLM_BASE_URL)",
    "openai": "OpenAI GPT (.env OPENAI_API_KEY)",
}
# 고를 수 있는 OpenAI 모델. 첫 번째가 기본값이다.
OPENAI_MODELS = ["gpt-5-mini", "gpt-5", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1"]
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULTS = {"provider": "local", "openai_model": DEFAULT_OPENAI_MODEL}

_DOC_ID = "llm_global"
_CACHE_S = 10.0
_lock = threading.Lock()
_cache: tuple[float, dict] | None = None


def _collection():
    from system.db import (
        admin_settings_db,
    )  # 지연 import(DB가 없는 테스트·도구에서도 모듈은 불러진다)

    return admin_settings_db


def _normalize(doc: dict | None) -> dict:
    doc = doc or {}
    provider = doc.get("provider")
    model = doc.get("openai_model")
    return {
        "provider": provider if provider in PROVIDERS else DEFAULTS["provider"],
        "openai_model": model if model in OPENAI_MODELS else DEFAULT_OPENAI_MODEL,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


def get() -> dict:
    """현재 전역 설정. 10초 캐시."""
    global _cache
    with _lock:
        if _cache and time.monotonic() - _cache[0] < _CACHE_S:
            return dict(_cache[1])
    try:
        value = _normalize(_collection().find_one({"_id": _DOC_ID}))
    except Exception as e:  # DB 장애 시에도 LLM 호출은 계속되어야 한다
        logger.warning("전역 AI 모델 설정을 읽지 못해 이전 값을 씁니다: %s", e)
        value = dict(_cache[1]) if _cache else _normalize(None)
    with _lock:
        _cache = (time.monotonic(), value)
    return dict(value)


def openai_api_key() -> str | None:
    """서버 .env 의 OpenAI 키(값은 밖으로 내보내지 않는다)."""
    for name in ("OPENAI_API_KEY", "LLM_FALLBACK_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def save(provider: str, openai_model: str | None, by: str | None = None) -> dict:
    """관리자가 고른 값을 저장한다. 잘못된 값이면 ValueError."""
    global _cache
    if provider not in PROVIDERS:
        raise ValueError("알 수 없는 모델 종류입니다.")
    model = openai_model or DEFAULT_OPENAI_MODEL
    if model not in OPENAI_MODELS:
        raise ValueError("고를 수 없는 OpenAI 모델입니다.")
    if provider == "openai" and not openai_api_key():
        raise ValueError(
            "서버 .env 에 OPENAI_API_KEY 가 없어 OpenAI 모델을 쓸 수 없습니다."
        )
    doc = {
        "provider": provider,
        "openai_model": model,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_by": by,
    }
    _collection().update_one({"_id": _DOC_ID}, {"$set": doc}, upsert=True)
    with _lock:
        _cache = (time.monotonic(), _normalize(doc))
    return get()


def openai_target() -> tuple[str, str, str] | None:
    """전역 설정이 OpenAI이고 키가 있으면 (base_url, api_key, model), 아니면 None."""
    cfg = get()
    if cfg["provider"] != "openai":
        return None
    key = openai_api_key()
    if not key:
        logger.warning(
            "전역 AI 모델이 OpenAI로 설정됐지만 OPENAI_API_KEY 가 없어 로컬 LLM을 씁니다"
        )
        return None
    return OPENAI_BASE_URL, key, cfg["openai_model"]


def describe() -> str:
    """사람이 읽는 현재 서버 기본 모델 이름."""
    target = openai_target()
    return f"OpenAI {target[2]}" if target else "로컬 LLM"


def status() -> dict:
    """관리자 화면용 상태(비밀 값 없음)."""
    from .config import get_settings

    cfg = get()
    return {
        **cfg,
        "providers": PROVIDERS,
        "openai_models": OPENAI_MODELS,
        "default_openai_model": DEFAULT_OPENAI_MODEL,
        "openai_key_set": bool(openai_api_key()),
        "local_base_url": get_settings().base_url,
        "active": describe(),
    }
