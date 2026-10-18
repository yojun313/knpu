"""Shared, account scoped LLM activity. Prompts and responses are never public list fields."""

import asyncio
import contextvars
import functools
import inspect
import re
import threading
import time
import uuid
from datetime import datetime, timezone, timedelta

_request = contextvars.ContextVar("llm_request", default=None)
_current = contextvars.ContextVar("llm_activity", default=None)
_indexed = False
STALE_SECONDS = 180


def collection():
    from system.db import llm_activity_db

    return llm_activity_db


def ensure_indexes():
    global _indexed
    if _indexed:
        return
    col = collection()
    col.create_index([("uid", 1), ("status", 1), ("created_ts", -1)])
    col.create_index([("status", 1), ("heartbeat_ts", 1)])
    col.create_index("expires_at", expireAfterSeconds=0)
    _indexed = True


def expire_stale():
    collection().update_many(
        {"status": "running", "heartbeat_ts": {"$lt": time.time() - STALE_SECONDS}},
        {
            "$set": {
                "status": "interrupted",
                "stage": "서버 연결이 중단되었습니다.",
                "finished_ts": time.time(),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
            }
        },
    )


def public(doc):
    keys = (
        "service",
        "title",
        "kind",
        "project_id",
        "status",
        "stage",
        "created_ts",
        "finished_ts",
        "path",
        "error",
    )
    result = {"id": doc["_id"], **{k: doc.get(k) for k in keys}}
    # Older activity records used a route that these applications never exposed.
    if (
        result["service"] in {"kemkim", "statistics", "network"}
        and result["project_id"]
        and result["path"] == "/view/" + result["project_id"]
    ):
        result["path"] = "/viewer/" + result["project_id"]
    return result


class Activity:
    def __init__(
        self,
        *,
        uid=None,
        service=None,
        title="AI 응답 생성",
        kind="llm",
        project_id=None,
        path=None,
        job_id=None,
    ):
        ctx = _request.get() or {}
        scope = ctx.get("scope") or {}
        user = scope.get("state", {}).get("user") or {}
        if not user and scope:
            from fastapi import HTTPException, Request
            from system.account import _session_user

            try:
                user = _session_user(Request(scope))
            except HTTPException:
                pass
        matched = re.search(r"/projects/([^/]+)", scope.get("path", ""))
        project_id = project_id or (matched.group(1) if matched else None)
        self.id = job_id or uuid.uuid4().hex
        self.doc = {
            "_id": self.id,
            "uid": uid or user.get("uid"),
            "service": service or ctx.get("service") or "system",
            "title": title[:180],
            "kind": kind,
            "project_id": project_id,
            "path": path
            or (
                "/viewer/" + project_id
                if project_id
                else "/git"
                if (service or ctx.get("service")) == "admin"
                else "/"
            ),
            "status": "running",
            "stage": "AI 작업을 실행하고 있습니다.",
            "created_ts": time.time(),
            "heartbeat_ts": time.time(),
        }
        self.stop = threading.Event()
        self.token = None

    def start(self):
        ensure_indexes()
        col = collection()
        col.insert_one(self.doc)
        threading.Thread(target=self._heartbeat, daemon=True).start()
        return self

    def _heartbeat(self):
        while not self.stop.wait(15):
            try:
                collection().update_one(
                    {"_id": self.id, "status": "running"},
                    {"$set": {"heartbeat_ts": time.time()}},
                )
            except Exception:
                import logging

                logging.getLogger(__name__).exception("AI 작업 heartbeat 저장 실패")

    def update(self, **fields):
        collection().update_one(
            {"_id": self.id, "status": "running"},
            {"$set": {**fields, "heartbeat_ts": time.time()}},
        )

    def finish(self, error=None, interrupted=False):
        self.stop.set()
        collection().update_one(
            {"_id": self.id, "status": "running"},
            {
                "$set": {
                    "status": "interrupted"
                    if interrupted
                    else "error"
                    if error
                    else "done",
                    "stage": "작업이 중단되었습니다."
                    if interrupted
                    else "실패"
                    if error
                    else "완료",
                    "error": str(error)[:500] if error else None,
                    "finished_ts": time.time(),
                    "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
                }
            },
        )

    def __enter__(self):
        self.start()
        self.token = _current.set(self)
        return self

    def __exit__(self, typ, error, tb):
        try:
            self.finish(
                error,
                typ is not None
                and issubclass(typ, (asyncio.CancelledError, GeneratorExit)),
            )
        finally:
            _current.reset(self.token)


def stage(text):
    activity = _current.get()
    if activity:
        activity.update(stage=str(text)[:300])


def tracked(title="AI 응답 생성", service=None, when=None):
    """Nested LLM calls share their outer operation instead of creating duplicate rows."""

    def decorate(fn):
        def eligible(args, kwargs):
            return when is None or when(
                inspect.signature(fn).bind_partial(*args, **kwargs).arguments
            )

        def context(args, kwargs):
            params = inspect.signature(fn).bind_partial(*args, **kwargs).arguments
            return Activity(uid=params.get("uid"), service=service, title=title)

        if inspect.isasyncgenfunction(fn):

            @functools.wraps(fn)
            async def generator(*args, **kwargs):
                if _current.get() or not eligible(args, kwargs):
                    async for part in fn(*args, **kwargs):
                        yield part
                else:
                    with context(args, kwargs):
                        async for part in fn(*args, **kwargs):
                            yield part

            return generator
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_call(*args, **kwargs):
                if _current.get() or not eligible(args, kwargs):
                    return await fn(*args, **kwargs)
                with context(args, kwargs) as activity:
                    result = await fn(*args, **kwargs)
                    if getattr(result, "status_code", 200) >= 400:
                        activity.finish("AI 요청에 실패했습니다.")
                    return result

            return async_call

        @functools.wraps(fn)
        def call(*args, **kwargs):
            if _current.get() or not eligible(args, kwargs):
                return fn(*args, **kwargs)
            with context(args, kwargs) as activity:
                result = fn(*args, **kwargs)
                if getattr(result, "status_code", 200) >= 400:
                    activity.finish("AI 요청에 실패했습니다.")
                return result

        return call

    return decorate


def start_background(coro, *, outcome=None, **kwargs):
    try:
        activity = Activity(**kwargs).start()
    except BaseException:
        coro.close()
        raise

    async def run():
        token = _current.set(activity)
        try:
            result = await coro
            state = outcome() if outcome else {}
            activity.finish(
                state.get("error") if state.get("status") == "error" else None
            )
            return result
        except BaseException as e:
            activity.finish(e, isinstance(e, asyncio.CancelledError))
            raise
        finally:
            _current.reset(token)

    task = asyncio.create_task(run())

    def completed(t):
        if t.cancelled() and not activity.stop.is_set():
            coro.close()
            activity.finish(interrupted=True)

    task.add_done_callback(completed)
    return task


class RequestContextMiddleware:
    def __init__(self, app, service):
        self.app, self.service = app, service

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = _request.set({"scope": scope, "service": self.service})
        try:
            await self.app(scope, receive, send)
        finally:
            _request.reset(token)


def register(app, service):
    from fastapi import HTTPException, Request
    from fastapi.responses import JSONResponse

    app.add_middleware(RequestContextMiddleware, service=service)

    def user(request):
        # /shared-ui assets bypass AuthMiddleware; validate the live account here.
        from system.account import _session_user

        return _session_user(request)

    @app.get("/shared-ui/llm-activity", include_in_schema=False)
    def listing(request: Request, scope: str = "mine", project_id: str | None = None):
        u = user(request)
        expire_stale()
        q = {} if scope == "all" and u.get("role") == "admin" else {"uid": u["uid"]}
        q["status"] = "running"
        if project_id:
            q["project_id"] = project_id
        items = [
            public(d) for d in collection().find(q).sort("created_ts", -1).limit(200)
        ]
        return JSONResponse(
            {"items": items, "is_admin": u.get("role") == "admin"},
            headers={"cache-control": "no-store"},
        )

    # Desktop calls with personal API keys still report their lifecycle to the server.
    @app.post("/api/llm-activity", include_in_schema=False)
    async def desktop_start(request: Request):
        u = user(request)
        ensure_indexes()
        expire_stale()
        if (
            collection().count_documents(
                {"uid": u["uid"], "kind": "desktop", "status": "running"}
            )
            >= 20
        ):
            raise HTTPException(429, "동시에 실행할 수 있는 AI 작업 수를 초과했습니다.")
        a = Activity(
            uid=u["uid"],
            service="manager",
            kind="desktop",
            title="MANAGER AI 분석",
            path="/board",
        )
        # The desktop sends heartbeats, so no local thread owns this operation.
        collection().insert_one(a.doc)
        return {"id": a.id}

    @app.patch("/api/llm-activity/{job_id}", include_in_schema=False)
    async def desktop_update(job_id: str, request: Request):
        u = user(request)
        doc = collection().find_one(
            {"_id": job_id, "uid": u["uid"], "kind": "desktop", "status": "running"}
        )
        if not doc:
            raise HTTPException(404, "AI 작업을 찾을 수 없습니다.")
        body = await request.json()
        a = Activity(job_id=job_id)
        if body.get("status") in ("done", "error"):
            a.finish(
                "MANAGER AI 요청에 실패했습니다." if body["status"] == "error" else None
            )
        else:
            a.update(stage="MANAGER AI 분석을 실행하고 있습니다.")
        return {"ok": True}
