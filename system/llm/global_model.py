"""전역 AI 모델 설정 — 관리자 대시보드에서 정하는 '서버 기본 모델'의 우선순위 목록.

모든 서비스가 system.llm(chat/achat/astream)을 부를 때 이 목록을 위에서부터 차례로 시도하고,
호출이 실패하면 다음 순위로 넘어간다. 목록에 들어가는 대상은 세 종류다.

- local : .env 의 로컬 LLM(LLM_BASE_URL). 기본 제공이며 지울 수 없고 끌 수만 있다.
- openai: .env 의 OPENAI_API_KEY 로 부르는 OpenAI 모델. 기본 제공이며 모델을 고를 수 있다.
- custom: 관리자가 추가한 OpenAI 호환 API(vLLM·Ollama·OpenRouter·Groq 등). 주소·키·모델을 직접 넣는다.
          키는 서버 비밀값으로 암호화해 저장하고 화면에는 끝 4자리만 돌려준다.

켜진 대상이 로컬 LLM 하나뿐이면 예전처럼 .env 의 폴백 설정(LLM_FALLBACK_*)을 뒤에 붙인다.
설정은 systems DB의 admin_settings 컬렉션(_id = "llm_global")에 두고, 프로세스마다 짧게 캐시해
서비스를 재시작하지 않아도 몇 초 안에 반영된다. DB를 읽을 수 없으면 마지막 값(없으면 기본값)을 쓴다.
사용자(관리자 포함)는 개인 API를 따로 설정할 수 없고, 모든 호출이 이 목록을 따른다.
"""

import logging
import os
import re
import secrets
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

KINDS = {
    "local": "로컬 LLM (.env LLM_BASE_URL)",
    "openai": "OpenAI GPT (.env OPENAI_API_KEY)",
    "custom": "OpenAI 호환 API",
}
# 기본 제공 OpenAI 대상에서 고를 수 있는 모델. 첫 번째가 기본값이다.
OPENAI_MODELS = ["gpt-5-mini", "gpt-5", "gpt-5-nano", "gpt-4.1-mini", "gpt-4.1"]
DEFAULT_OPENAI_MODEL = "gpt-5-mini"
OPENAI_BASE_URL = "https://api.openai.com/v1"
MAX_ENTRIES = 20

_DOC_ID = "llm_global"
_CACHE_S = 10.0
_lock = threading.Lock()
_cache: tuple[float, dict] | None = None
_ID_RX = re.compile(r"^[a-z0-9]{1,24}$")


def _builtin(kind: str, enabled: bool, model: str | None = None) -> dict:
    return {
        "id": kind,
        "kind": kind,
        "name": "로컬 LLM" if kind == "local" else "OpenAI",
        "base_url": None,
        "model": model or (DEFAULT_OPENAI_MODEL if kind == "openai" else None),
        "enabled": enabled,
    }


DEFAULT_ENTRIES = [_builtin("local", True), _builtin("openai", False)]


def _collection():
    from system.db import (
        admin_settings_db,
    )  # 지연 import(DB가 없는 테스트·도구에서도 모듈은 불러진다)

    return admin_settings_db


def _clean_entry(raw: dict) -> dict | None:
    kind = raw.get("kind")
    if kind not in KINDS or not _ID_RX.match(str(raw.get("id") or "")):
        return None
    if kind == "openai":
        model = raw.get("model")
        return _builtin(
            "openai",
            bool(raw.get("enabled")),
            model if model in OPENAI_MODELS else DEFAULT_OPENAI_MODEL,
        )
    if kind == "local":
        return _builtin("local", bool(raw.get("enabled")))
    return {
        "id": raw["id"],
        "kind": "custom",
        "name": str(raw.get("name") or "OpenAI 호환 API")[:40],
        "base_url": raw.get("base_url"),
        "model": (raw.get("model") or None),
        "enabled": bool(raw.get("enabled")),
        "api_key_enc": raw.get("api_key_enc"),
        "key_hint": raw.get("key_hint", ""),
    }


def _normalize(doc: dict | None) -> dict:
    """저장된 문서를 우선순위 목록으로 정리한다. 예전 형식({provider, openai_model})도 읽는다."""
    doc = doc or {}
    if isinstance(doc.get("entries"), list):
        entries = [e for e in map(_clean_entry, doc["entries"]) if e]
    elif doc.get("provider") == "openai":
        entries = [
            _builtin("openai", True, doc.get("openai_model")),
            _builtin("local", True),
        ]
        entries[0] = _clean_entry(entries[0])
    else:
        entries = [dict(e) for e in DEFAULT_ENTRIES]
    # 기본 제공 대상은 항상 하나씩 있어야 한다(빠졌으면 맨 뒤에 꺼진 채로 붙인다)
    seen = set()
    out = []
    for e in entries:
        if e["id"] in seen:
            continue
        seen.add(e["id"])
        out.append(e)
    for kind in ("local", "openai"):
        if kind not in seen:
            out.append(_builtin(kind, False))
    return {
        "entries": out,
        "updated_at": doc.get("updated_at"),
        "updated_by": doc.get("updated_by"),
    }


def get() -> dict:
    """현재 전역 설정(우선순위 목록). 10초 캐시."""
    global _cache
    with _lock:
        if _cache and time.monotonic() - _cache[0] < _CACHE_S:
            return _copy(_cache[1])
    try:
        value = _normalize(_collection().find_one({"_id": _DOC_ID}))
    except Exception as e:  # DB 장애 시에도 LLM 호출은 계속되어야 한다
        logger.warning("전역 AI 모델 설정을 읽지 못해 이전 값을 씁니다: %s", e)
        value = _copy(_cache[1]) if _cache else _normalize(None)
    with _lock:
        _cache = (time.monotonic(), value)
    return _copy(value)


def _copy(value: dict) -> dict:
    return {**value, "entries": [dict(e) for e in value["entries"]]}


def openai_api_key() -> str | None:
    """서버 .env 의 OpenAI 키(값은 밖으로 내보내지 않는다)."""
    for name in ("OPENAI_API_KEY", "LLM_FALLBACK_API_KEY"):
        value = (os.getenv(name) or "").strip()
        if value:
            return value
    return None


def _decrypt(token: str | None) -> str | None:
    if not token:
        return None
    from .user_llm import _decrypt as dec

    return dec(token)


def _validate_url(url: str | None) -> str:
    url = (url or "").strip().rstrip("/")
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc or len(url) > 300:
        raise ValueError(
            "API 주소는 http:// 또는 https:// 로 시작해야 합니다(예: https://api.example.com/v1)."
        )
    return url


def save(entries: list[dict], by: str | None = None) -> dict:
    """관리자가 정한 우선순위 목록을 저장한다(목록 순서 = 우선순위). 잘못된 값이면 ValueError.

    custom 항목의 api_key 가 비어 있으면 기존 키를 그대로 두고, clear_key 가 참이면 지운다.
    """
    global _cache
    if not isinstance(entries, list) or not entries:
        raise ValueError("우선순위 목록이 비어 있습니다.")
    if len(entries) > MAX_ENTRIES:
        raise ValueError(f"대상은 최대 {MAX_ENTRIES}개까지 둘 수 있습니다.")
    old = {e["id"]: e for e in get()["entries"]}
    out, seen = [], set()
    for raw in entries:
        if not isinstance(raw, dict):
            raise ValueError("목록 형식이 올바르지 않습니다.")
        kind = raw.get("kind")
        eid = str(raw.get("id") or "")
        if kind not in KINDS:
            raise ValueError("알 수 없는 대상 종류입니다.")
        if kind in ("local", "openai"):
            eid = kind
        elif not _ID_RX.match(eid) or eid in ("local", "openai"):
            eid = secrets.token_hex(6)  # 새로 추가한 항목
        if eid in seen:
            raise ValueError("같은 대상이 두 번 들어 있습니다.")
        seen.add(eid)
        enabled = bool(raw.get("enabled"))

        if kind == "local":
            out.append(_builtin("local", enabled))
            continue
        if kind == "openai":
            model = raw.get("model") or DEFAULT_OPENAI_MODEL
            if model not in OPENAI_MODELS:
                raise ValueError("고를 수 없는 OpenAI 모델입니다.")
            if enabled and not openai_api_key():
                raise ValueError(
                    "서버 .env 에 OPENAI_API_KEY 가 없어 OpenAI를 켤 수 없습니다."
                )
            out.append(_builtin("openai", enabled, model))
            continue

        name = str(raw.get("name") or "").strip()[:40]
        if not name:
            raise ValueError("추가한 API의 이름을 입력해 주시기 바랍니다.")
        base_url = _validate_url(raw.get("base_url"))
        model = str(raw.get("model") or "").strip()[:200] or None
        prev = old.get(eid) if old.get(eid, {}).get("kind") == "custom" else {}
        key_enc, hint = prev.get("api_key_enc"), prev.get("key_hint", "")
        new_key = str(raw.get("api_key") or "").strip()
        if raw.get("clear_key"):
            key_enc, hint = None, ""
        if new_key:
            if len(new_key) > 500:
                raise ValueError("API 키가 너무 깁니다.")
            from .user_llm import _encrypt

            key_enc, hint = _encrypt(new_key), new_key[-4:]
        out.append(
            {
                "id": eid,
                "kind": "custom",
                "name": name,
                "base_url": base_url,
                "model": model,
                "enabled": enabled,
                "api_key_enc": key_enc,
                "key_hint": hint,
            }
        )
    for kind in ("local", "openai"):
        if kind not in seen:
            raise ValueError(
                "기본 대상(로컬 LLM·OpenAI)은 지울 수 없습니다. 끄기만 할 수 있습니다."
            )
    if not any(e["enabled"] for e in out):
        raise ValueError("최소 한 개의 대상은 켜 두어야 합니다.")

    doc = {
        "entries": out,
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "updated_by": by,
    }
    _collection().update_one(
        {"_id": _DOC_ID},
        {"$set": doc, "$unset": {"provider": "", "openai_model": ""}},
        upsert=True,
    )
    with _lock:
        _cache = (time.monotonic(), _normalize(doc))
    return status()  # 비밀 값(암호화된 키)은 돌려주지 않는다


def connection(entry: dict, local_model: str | None = None) -> dict | None:
    """한 대상의 접속 정보 {label, base_url, api_key, model}. 지금 쓸 수 없으면 None."""
    from .config import get_settings

    kind = entry.get("kind")
    if kind == "local":
        s = get_settings()
        return {
            "label": entry["name"],
            "base_url": s.base_url,
            "api_key": s.api_key,
            "model": local_model or s.model,
        }
    if kind == "openai":
        key = openai_api_key()
        if not key:
            return None
        return {
            "label": entry["name"],
            "base_url": OPENAI_BASE_URL,
            "api_key": key,
            "model": entry.get("model") or DEFAULT_OPENAI_MODEL,
        }
    if kind == "custom" and entry.get("base_url"):
        key = _decrypt(entry.get("api_key_enc"))
        if entry.get("api_key_enc") and not key:
            return None  # 저장된 키를 풀 수 없으면 인증 없이 보내지 않는다
        return {
            "label": entry["name"],
            "base_url": entry["base_url"],
            "api_key": key or "not-needed",
            "model": entry.get("model")
            or None,  # 비우면 서버의 첫 모델을 자동으로 쓴다
        }
    return None


def chain(local_model: str | None = None) -> list[dict]:
    """켜진 대상을 우선순위대로 접속 정보로 바꾼 목록(쓸 수 없는 대상은 건너뛴다)."""
    out = []
    for e in get()["entries"]:
        if not e.get("enabled"):
            continue
        conn = connection(e, local_model)
        if conn:
            out.append({**conn, "id": e["id"], "kind": e["kind"]})
        else:
            logger.warning(
                "전역 AI 모델 '%s'을(를) 지금 쓸 수 없어 건너뜁니다", e.get("name")
            )
    return out


def _entry_text(e: dict) -> str:
    if e["kind"] == "openai":
        return f"OpenAI {e.get('model') or DEFAULT_OPENAI_MODEL}"
    if e["kind"] == "custom":
        return f"{e['name']}" + (f" ({e['model']})" if e.get("model") else "")
    return e["name"]


def describe() -> str:
    """사람이 읽는 현재 우선순위(관리자용)."""
    names = [_entry_text(e) for e in get()["entries"] if e.get("enabled")]
    return " → ".join(names) or "로컬 LLM"


def status() -> dict:
    """관리자 화면용 상태(비밀 값 없음)."""
    from .config import get_settings

    cfg = get()
    entries = []
    for e in cfg["entries"]:
        item = {k: v for k, v in e.items() if k != "api_key_enc"}
        if e["kind"] == "custom":
            item["key_set"] = bool(e.get("api_key_enc"))
        entries.append(item)
    return {
        "entries": entries,
        "updated_at": cfg.get("updated_at"),
        "updated_by": cfg.get("updated_by"),
        "kinds": KINDS,
        "openai_models": OPENAI_MODELS,
        "default_openai_model": DEFAULT_OPENAI_MODEL,
        "openai_key_set": bool(openai_api_key()),
        "local_base_url": get_settings().base_url,
        "max_entries": MAX_ENTRIES,
        "active": describe(),
    }


def draft_connection(raw: dict) -> dict:
    """저장 전 화면의 항목으로 접속 정보를 만든다(연결 확인·모델 불러오기용).

    키 칸이 비어 있으면 같은 id로 저장된 키를 쓴다. 잘못된 값이면 ValueError.
    """
    kind = raw.get("kind")
    if kind in ("local", "openai"):
        entry = _builtin(kind, True, raw.get("model") if kind == "openai" else None)
        if kind == "openai" and entry["model"] not in OPENAI_MODELS:
            raise ValueError("고를 수 없는 OpenAI 모델입니다.")
        conn = connection(entry)
        if not conn:
            raise ValueError("서버 .env 에 OPENAI_API_KEY 가 없습니다.")
        return conn
    if kind != "custom":
        raise ValueError("알 수 없는 대상 종류입니다.")
    key = str(raw.get("api_key") or "").strip()
    if not key and not raw.get("clear_key"):
        saved = next((e for e in get()["entries"] if e["id"] == raw.get("id")), None)
        key = _decrypt(saved.get("api_key_enc")) if saved else None
    return {
        "label": str(raw.get("name") or "OpenAI 호환 API")[:40],
        "base_url": _validate_url(raw.get("base_url")),
        "api_key": key or "not-needed",
        "model": str(raw.get("model") or "").strip() or None,
    }
