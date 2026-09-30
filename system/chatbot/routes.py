"""챗봇 API — mount_shared_ui 가 모든 사이트에 /shared-ui/chatbot/api/* 로 붙인다.

/shared-ui/* 는 각 사이트 인증 미들웨어가 로그인 없이 통과시키는 경로라서, 로그인 여부는 여기서
공통 세션 쿠키로 직접 확인한다(auth.current_user).

대화 기록
- 로그인한 사용자: 대화를 여러 개 만들고 전환할 수 있으며 모두 서버(~/.knpu_chatbot/conversations/<uid>/)에
  저장된다(홈페이지 안내 · 구성원용 둘 다). 진행 상황도 함께 저장되어 다른 사이트 · 기기에서 열어도 이어진다.
- 로그인하지 않은 방문자(홈페이지 안내만 가능): 서버에 남기지 않고 브라우저에만 저장한다.
  요청 하나는 이 프로세스의 작업으로 돌려 폴링하고, IP 당 요청 수를 제한한다.
"""

import asyncio
import json
import logging
import os
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timezone

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from . import agent
from .auth import current_user
from .config import data_dir

logger = logging.getLogger(__name__)

_MAX_MESSAGES = 200  # 대화 하나에 남기는 메시지 수
_MAX_CONVERSATIONS = 200  # 사용자당 대화 수
_STALE_PENDING_S = 120
_PUBLIC_LIMIT = (15, 600)  # 비로그인: 10분에 15번
_USER_LIMIT = (60, 3600)  # 로그인: 1시간에 60번

_lock = threading.Lock()
_anon_jobs: dict[str, dict] = {}
_live: set[str] = set()  # 이 프로세스에서 돌고 있는 작업 id
_hits: dict[str, deque] = {}
_ID_RX = re.compile(r"^[a-f0-9]{8,40}$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rate_ok(key: str, limit: tuple[int, int]) -> bool:
    count, window = limit
    now = time.time()
    q = _hits.setdefault(key, deque())
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= count:
        return False
    q.append(now)
    return True


# ── 로그인 사용자 대화 저장소 (사이트 · 기기 공용) ───────────────────────────────


def _user_dir(uid: str):
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", uid)[:80]
    folder = data_dir() / "conversations" / safe
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def _conv_file(uid: str, cid: str):
    if not _ID_RX.match(cid or ""):
        raise HTTPException(400, "잘못된 대화 id 입니다.")
    return _user_dir(uid) / f"{cid}.json"


def _load(uid: str, cid: str) -> dict | None:
    try:
        data = json.loads(_conv_file(uid, cid).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None


def _save(uid: str, conv: dict) -> None:
    conv["messages"] = conv.get("messages", [])[-_MAX_MESSAGES:]
    path = _conv_file(uid, conv["id"])
    tmp = path.with_name(f".{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(conv, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _update(uid: str, cid: str, fn) -> dict | None:
    with _lock:
        conv = _load(uid, cid)
        if conv is None:
            return None
        fn(conv)
        _save(uid, conv)
        return conv


def _settle(uid: str, conv: dict) -> dict:
    """다른 프로세스에서 돌다 서버 재시작 등으로 멈춘 '답변 중'을 실패로 정리한다."""
    now = time.time()
    stale = {
        m.get("job_id")
        for m in conv.get("messages", [])
        if m.get("pending")
        and m.get("job_id") not in _live
        and now - float(m.get("beat") or 0) > _STALE_PENDING_S
    }
    if not stale:
        return conv

    def fix(c):
        for m in c["messages"]:
            if m.get("pending") and m.get("job_id") in stale:
                m.pop("pending", None)
                m.update(
                    error=True,
                    content="답변을 준비하던 중 서버가 다시 시작되어 중단되었어요. 다시 질문해 주세요.",
                )

    return _update(uid, conv["id"], fix) or conv


def _summary(conv: dict) -> dict:
    msgs = conv.get("messages", [])
    return {
        "id": conv["id"],
        "mode": conv.get("mode"),
        "title": conv.get("title") or "새 대화",
        "created_at": conv.get("created_at"),
        "updated_at": conv.get("updated_at"),
        "count": sum(1 for m in msgs if m.get("role") == "user"),
        "pending": any(m.get("pending") for m in msgs),
    }


def _list(uid: str, mode: str | None = None) -> list[dict]:
    items = []
    for f in _user_dir(uid).glob("*.json"):
        try:
            conv = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(conv, dict) and (not mode or conv.get("mode") == mode):
            items.append(_summary(conv))
    items.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    return items


def _create(uid: str, mode: str) -> dict:
    now = _now()
    conv = {
        "id": uuid.uuid4().hex,
        "mode": mode,
        "title": "",
        "created_at": now,
        "updated_at": now,
        "messages": [],
    }
    with _lock:
        _save(uid, conv)
        # 오래된 대화부터 정리해 사용자당 개수를 제한한다
        for old in _list(uid)[_MAX_CONVERSATIONS:]:
            try:
                _conv_file(uid, old["id"]).unlink()
            except OSError:
                pass
    return conv


def _client_msgs(items: list[dict]) -> list[dict]:
    keys = (
        "role",
        "content",
        "pending",
        "stage",
        "steps",
        "sources",
        "error",
        "created_at",
        "job_id",
        "llm",
    )
    return [{k: m[k] for k in keys if k in m} for m in items]


def _require_user(request: Request) -> dict:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "로그인이 필요합니다.")
    return user


# ── 라우트 ──────────────────────────────────────────────────────────────────────


def register(app, *, public: bool) -> None:
    """public=True 는 홈페이지(외부인용 '홈페이지 안내' 챗봇을 켜는 사이트)."""
    base = "/shared-ui/chatbot/api"

    def mode_ok(mode: str) -> str:
        if mode not in ("public", "member"):
            raise HTTPException(400, "잘못된 챗봇 종류입니다.")
        if mode == "public" and not public:
            raise HTTPException(403, "이 사이트에서는 구성원용 챗봇만 쓸 수 있어요.")
        return mode

    @app.get(f"{base}/config", include_in_schema=False)
    def chatbot_config(request: Request):
        user = current_user(request)
        return JSONResponse(
            {
                "user": {"name": user["name"]} if user else None,
                "public": public,
                "member": bool(user),
            },
            headers={"cache-control": "no-store"},
        )

    @app.get(f"{base}/conversations", include_in_schema=False)
    def chatbot_list(request: Request, mode: str = "member"):
        user = _require_user(request)
        return JSONResponse(
            {"conversations": _list(user["uid"], mode_ok(mode))},
            headers={"cache-control": "no-store"},
        )

    @app.post(f"{base}/conversations", include_in_schema=False)
    async def chatbot_new(request: Request):
        user = _require_user(request)
        try:
            body = await request.json()
        except ValueError:
            body = {}
        conv = _create(user["uid"], mode_ok(str((body or {}).get("mode") or "member")))
        return _summary(conv)

    @app.get(f"{base}/conversations/{{cid}}", include_in_schema=False)
    def chatbot_get(request: Request, cid: str):
        user = _require_user(request)
        conv = _load(user["uid"], cid)
        if not conv:
            raise HTTPException(404, "대화를 찾을 수 없어요.")
        conv = _settle(user["uid"], conv)
        return JSONResponse(
            {**_summary(conv), "messages": _client_msgs(conv.get("messages", []))},
            headers={"cache-control": "no-store"},
        )

    @app.patch(f"{base}/conversations/{{cid}}", include_in_schema=False)
    async def chatbot_rename(request: Request, cid: str):
        user = _require_user(request)
        body = await request.json()
        title = str((body or {}).get("title") or "").strip()[:80]
        conv = _update(user["uid"], cid, lambda c: c.update(title=title))
        if not conv:
            raise HTTPException(404, "대화를 찾을 수 없어요.")
        return _summary(conv)

    @app.delete(f"{base}/conversations/{{cid}}", include_in_schema=False)
    def chatbot_delete(request: Request, cid: str):
        user = _require_user(request)
        conv = _load(user["uid"], cid)
        if not conv:
            raise HTTPException(404, "대화를 찾을 수 없어요.")
        if any(
            m.get("pending") and m.get("job_id") in _live
            for m in conv.get("messages", [])
        ):
            raise HTTPException(409, "답변을 준비하는 중에는 대화를 지울 수 없어요.")
        _conv_file(user["uid"], cid).unlink(missing_ok=True)
        return {"ok": True}

    @app.post(f"{base}/ask", include_in_schema=False)
    async def chatbot_ask(request: Request):
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(400, "요청 형식이 올바르지 않습니다.")
        mode = mode_ok("member" if body.get("mode") == "member" else "public")
        question = str(body.get("question") or "").strip()
        if not question:
            raise HTTPException(400, "질문을 입력해 주세요.")
        if len(question) > 2000:
            raise HTTPException(400, "질문이 너무 길어요(2,000자 이하).")
        user = current_user(request)
        if mode == "member" and not user:
            raise HTTPException(401, "구성원용 챗봇은 로그인이 필요합니다.")

        if user:
            return await _ask_saved(
                user, mode, question, str(body.get("conversation_id") or "")
            )

        # 비로그인 방문자: 서버에 저장하지 않는다(브라우저가 기록을 들고 온다)
        ip = (
            (
                request.headers.get("x-forwarded-for")
                or (request.client.host if request.client else "?")
            )
            .split(",")[0]
            .strip()
        )
        if not _rate_ok(f"ip:{ip}", _PUBLIC_LIMIT):
            raise HTTPException(429, "질문이 너무 잦아요. 잠시 후 다시 시도해 주세요.")
        raw = body.get("history") if isinstance(body.get("history"), list) else []
        history = [h for h in raw if isinstance(h, dict)][-8:]
        job_id = uuid.uuid4().hex
        job = {
            "status": "running",
            "stage": "질문을 이해하는 중",
            "steps": [],
            "result": None,
            "error": None,
            "created": time.time(),
        }
        for jid in [
            j for j, v in _anon_jobs.items() if time.time() - v["created"] > 1800
        ]:
            _anon_jobs.pop(jid, None)
        _anon_jobs[job_id] = job

        def emit(ev):
            if ev["type"] == "step":
                job["steps"].append(ev["label"])
            if ev["type"] in ("step", "stage"):
                job["stage"] = ev["label"]

        async def worker():
            try:
                job["result"] = await agent.run(
                    "public", question, history, None, "", emit
                )  # 서버 공용(로컬) LLM
                job["status"] = "done"
            except Exception as e:
                logger.exception("홈페이지 챗봇 실패")
                job["status"], job["error"] = (
                    "error",
                    str(e) or "답변을 만들지 못했어요.",
                )

        asyncio.create_task(worker())
        return JSONResponse({"ok": True, "job_id": job_id}, status_code=202)

    async def _ask_saved(user: dict, mode: str, question: str, cid: str):
        uid = user["uid"]
        if not _rate_ok(f"u:{uid}", _USER_LIMIT):
            raise HTTPException(429, "질문이 너무 잦아요. 잠시 후 다시 시도해 주세요.")
        conv = _load(uid, cid) if _ID_RX.match(cid or "") else None
        if conv is None or conv.get("mode") != mode:
            conv = _create(uid, mode)
        conv = _settle(uid, conv)
        if any(m.get("pending") for m in conv["messages"]):
            raise HTTPException(
                409, "이 대화에서 이전 질문에 대한 답변을 준비하고 있어요."
            )
        history = [
            {"role": m["role"], "content": m["content"]}
            for m in conv["messages"]
            if not m.get("pending") and not m.get("error") and m.get("content")
        ][-8:]
        cid = conv["id"]
        job_id = uuid.uuid4().hex
        now = _now()

        def start(c):
            if not c.get("title"):
                c["title"] = re.sub(r"\s+", " ", question)[:40]
            c["updated_at"] = now
            c["messages"] += [
                {"role": "user", "content": question, "created_at": now},
                {
                    "role": "assistant",
                    "pending": True,
                    "job_id": job_id,
                    "stage": "질문을 이해하는 중",
                    "steps": [],
                    "created_at": now,
                    "beat": time.time(),
                },
            ]

        _update(uid, cid, start)
        _live.add(job_id)

        def emit(ev):
            def fix(c):
                for m in c["messages"]:
                    if m.get("job_id") == job_id and m.get("pending"):
                        if ev["type"] == "stage":
                            m["stage"] = ev["label"]
                        elif ev["type"] == "step":
                            m["steps"] = (m.get("steps") or []) + [ev["label"]]
                            m["stage"] = ev["label"]
                        m["beat"] = time.time()

            _update(uid, cid, fix)

        async def heartbeat():
            # LLM 호출 하나가 길어도 다른 프로세스가 '멈춘 작업'으로 오해하지 않게
            while job_id in _live:
                await asyncio.sleep(20)
                if job_id in _live:
                    await asyncio.to_thread(emit, {"type": "beat"})

        async def worker():
            beat_task = asyncio.create_task(heartbeat())
            try:
                result = await agent.run(
                    mode, question, history, uid, user["name"], emit
                )
                msg = {
                    "role": "assistant",
                    "content": result["answer"],
                    "sources": result["sources"],
                    "steps": result["steps"],
                    "llm": result["llm"],
                    "job_id": job_id,
                    "created_at": _now(),
                }
            except Exception as e:
                logger.exception("챗봇 실패")
                msg = {
                    "role": "assistant",
                    "error": True,
                    "content": str(e) or "답변을 만들지 못했어요.",
                    "job_id": job_id,
                    "created_at": _now(),
                }
            finally:
                _live.discard(job_id)
                beat_task.cancel()

            def done(c):
                c["messages"] = [
                    msg
                    if (m.get("job_id") == job_id and m.get("role") == "assistant")
                    else m
                    for m in c["messages"]
                ]
                c["updated_at"] = _now()

            await asyncio.to_thread(_update, uid, cid, done)

        asyncio.create_task(worker())
        return JSONResponse(
            {"ok": True, "job_id": job_id, "conversation_id": cid}, status_code=202
        )

    @app.get(f"{base}/jobs/{{job_id}}", include_in_schema=False)
    def chatbot_job(job_id: str):
        job = _anon_jobs.get(job_id)
        if not job:
            raise HTTPException(
                404, "작업을 찾을 수 없어요. 페이지를 새로 고쳐 다시 질문해 주세요."
            )
        return JSONResponse(
            {k: job[k] for k in ("status", "stage", "steps", "result", "error")},
            headers={"cache-control": "no-store"},
        )
