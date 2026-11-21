"""챗봇 도구 등록소 — 도구를 함수 하나로 추가한다.

    from system.chatbot.registry import tool

    @tool(
        "my_tool",                       # 모델이 부르는 이름
        "무엇을 하는 도구인지 한 줄",        # 시스템 지침에 그대로 들어가는 설명
        {"query": "검색어", "limit": "(선택) 개수"},   # 인자 이름 → 설명. "(선택)"으로 시작하면 생략 가능
        modes=("member",),               # public(홈페이지 안내) / member(구성원용)
        label="내 도구 · {query}",         # 화면의 진행 단계 문구
        cache_s=60,                      # 같은 인자의 결과를 재사용할 시간(초). 사용자별 도구는 per_user=True
    )
    def my_tool(ctx, query="", limit=""):
        return {"count": 0, "results": []}   # dict 를 돌려준다. 실패는 ValueError("사용자에게 보일 이유")

도구 모듈을 두는 곳
- system/chatbot/toolsets/ 안의 모듈은 자동으로 불러온다.
- 다른 패키지의 도구는 환경 변수 CHATBOT_TOOL_MODULES="pkg.mod1,pkg.mod2" 로 더한다.
도구는 읽기 전용이어야 하고, 사용자 자료를 다루는 도구는 반드시 ctx.uid 로 본인 것만 조회한다.
"""

import importlib
import inspect
import json
import logging
import os
import pkgutil
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

logger = logging.getLogger(__name__)

MODES = ("public", "member")


@dataclass
class Context:
    """도구가 받는 호출 맥락."""

    mode: str = "public"
    uid: str | None = None
    user_name: str = ""
    role: str = ""

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


@dataclass
class Tool:
    name: str
    desc: str
    args: dict
    fn: Callable
    modes: tuple = MODES
    label: str = ""
    cache_s: float = 0
    per_user: bool = False
    group: str = ""
    reads: bool = (
        False  # 이 도구로 본 내용을 '실제로 읽은 본문'으로 친다(화면 문구 대조용)
    )
    optional: set = field(default_factory=set)

    def step_label(self, args: dict) -> str:
        if not self.label:
            return self.name
        safe = {k: str((args or {}).get(k) or "") for k in self.args}
        try:
            return self.label.format(**safe).strip(" ·")[:120] or self.name
        except (KeyError, IndexError, ValueError):
            return self.name


_tools: dict[str, Tool] = {}
_loaded = False
_load_lock = threading.Lock()
_cache: dict[str, tuple[float, dict]] = {}
_cache_lock = threading.Lock()
_CACHE_MAX = 400


def tool(
    name: str,
    desc: str,
    args: dict | None = None,
    *,
    modes: tuple = MODES,
    label: str = "",
    cache_s: float = 0,
    per_user: bool = False,
    group: str = "",
    reads: bool = False,
):
    """도구 등록 데코레이터. 같은 이름을 다시 등록하면 나중 것이 이긴다."""

    def deco(fn):
        a = dict(args or {})
        _tools[name] = Tool(
            name=name,
            desc=desc,
            args=a,
            fn=fn,
            modes=tuple(modes),
            label=label,
            cache_s=cache_s,
            per_user=per_user,
            group=group or fn.__module__.rsplit(".", 1)[-1],
            reads=reads,
            optional={k for k, v in a.items() if str(v).lstrip().startswith("(선택)")},
        )
        return fn

    return deco


def load() -> None:
    """toolsets 패키지와 CHATBOT_TOOL_MODULES 의 도구 모듈을 한 번만 불러온다."""
    global _loaded
    if _loaded:
        return
    with _load_lock:
        if _loaded:
            return
        from . import toolsets

        names = [
            f"{toolsets.__name__}.{m.name}"
            for m in pkgutil.iter_modules(toolsets.__path__)
            if not m.name.startswith("_")
        ]
        names += [
            m.strip()
            for m in (os.getenv("CHATBOT_TOOL_MODULES") or "").split(",")
            if m.strip()
        ]
        for mod in names:
            try:
                importlib.import_module(mod)
            except Exception:  # 도구 묶음 하나가 깨져도 나머지는 동작해야 한다
                logger.exception("챗봇 도구 모듈을 불러오지 못했습니다: %s", mod)
        _loaded = True


def get(name: str) -> Tool | None:
    load()
    return _tools.get(name)


def for_mode(mode: str) -> dict[str, Tool]:
    load()
    return {n: t for n, t in _tools.items() if mode in t.modes}


def prompt(mode: str) -> str:
    """시스템 지침에 넣는 도구 목록."""
    lines = []
    for name, t in for_mode(mode).items():
        arg = ", ".join(f'"{k}": {v}' for k, v in t.args.items())
        lines.append(f"- {name}({arg}) — {t.desc}")
    return "\n".join(lines)


def _cache_key(t: Tool, ctx: Context, args: dict) -> str:
    who = (ctx.uid or "") if t.per_user else ""
    return json.dumps(
        [t.name, who, args], ensure_ascii=False, sort_keys=True, default=str
    )


def run(ctx: Context, name: str, args: dict) -> dict:
    """도구 하나를 실행한다. 어떤 실패도 예외 대신 {"error": ...} 로 돌려 대화를 이어 간다."""
    allowed = for_mode(ctx.mode)
    t = allowed.get(name)
    if t is None:
        return {
            "error": f"사용할 수 없는 도구입니다: {name}. 가능한 도구: {', '.join(allowed)}"
        }
    args = args if isinstance(args, dict) else {}
    extra = set(args) - set(t.args)
    if extra:
        # 모르는 인자를 조용히 무시하면 엉뚱한 결과를 받게 되므로 오류로 알린다
        return {
            "error": f"{name} 에 없는 인자: {', '.join(sorted(extra))}. 가능한 인자: {', '.join(t.args) or '없음'}"
        }
    clean = {k: v for k, v in args.items() if v is not None and v != ""}
    key = _cache_key(t, ctx, clean) if t.cache_s else None
    if key:
        with _cache_lock:
            hit = _cache.get(key)
            if hit and time.monotonic() - hit[0] < t.cache_s:
                return hit[1]
    try:
        params = inspect.signature(t.fn).parameters
        kwargs = {k: v for k, v in clean.items() if k in params}
        result = t.fn(ctx, **kwargs)
        if not isinstance(result, dict):
            result = {"result": result}
    except ValueError as e:
        return {"error": str(e)}
    except Exception as e:
        logger.warning("챗봇 도구 %s 실패: %s", name, e)
        return {"error": f"{type(e).__name__}: {e}"}
    if key and not result.get("error"):
        with _cache_lock:
            if len(_cache) >= _CACHE_MAX:
                for old in sorted(_cache, key=lambda k: _cache[k][0])[
                    : _CACHE_MAX // 4
                ]:
                    _cache.pop(old, None)
            _cache[key] = (time.monotonic(), result)
    return result
