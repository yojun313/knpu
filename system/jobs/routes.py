import asyncio
import os
import time

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from system.jobs import store

_NO_STORE = {"cache-control": "no-store"}


def _user(request: Request) -> dict:
    user = (request.scope.get("state") or {}).get("user")
    if not user:
        raise HTTPException(401, "인증이 필요합니다")
    return user


def _owned(request: Request, job_id: str) -> tuple[dict, dict]:
    user = _user(request)
    job = store.get(job_id)
    if not job or (job.get("uid") != user["uid"] and user.get("role") != "admin"):
        raise HTTPException(404, "작업을 찾을 수 없습니다.")
    return user, job


def parse_schedule(value) -> float | None:
    """브라우저가 보낸 예약 시각(epoch ms 또는 s). 과거/너무 먼 미래는 거절."""
    if value in (None, "", 0):
        return None
    try:
        ts = float(value)
    except (TypeError, ValueError):
        raise HTTPException(400, "예약 시각 형식이 올바르지 않습니다.")
    if ts > 1e11:  # ms
        ts /= 1000.0
    now = time.time()
    if ts < now - 60:
        raise HTTPException(400, "예약 시각이 이미 지났습니다.")
    if ts > now + 60 * 86400:
        raise HTTPException(400, "예약은 60일 이내로만 걸 수 있습니다.")
    return ts


def register(app, service: str, runner) -> None:
    base = "/api/jobs"

    @app.get(base, include_in_schema=False)
    def jobs_list(request: Request, scope: str = "service", limit: int = 60):
        user = _user(request)
        q: dict = {"uid": user["uid"]}
        if scope == "everyone" and user.get("role") == "admin":
            q = {}
        if scope != "all":
            q["service"] = service
        limit = max(1, min(int(limit or 60), 200))
        col = store.collection()
        items = [
            store.public(j)
            for j in col.find(q, {"log": 0}).sort("created_ts", -1).limit(limit)
        ]
        active = sum(1 for j in items if j["status"] in store.ACTIVE)
        return JSONResponse(
            {
                "service": service,
                "items": items,
                "active": active,
                "max_concurrent": runner.max_concurrent,
                "now": time.time(),
            },
            headers=_NO_STORE,
        )

    @app.get(f"{base}/summary", include_in_schema=False)
    def jobs_summary(request: Request):
        """사이드바 배지용: 이 사용자의 진행 중/예약 작업 수와 최근 끝난 작업."""
        user = _user(request)
        col = store.collection()
        q = {"uid": user["uid"], "service": service}
        running = col.count_documents(
            {**q, "status": {"$in": list(store.RUNNING) + ["queued"]}}
        )
        scheduled = col.count_documents({**q, "status": "scheduled"})
        recent = [
            store.public(j)
            for j in col.find(
                {
                    **q,
                    "status": {"$in": list(store.FINISHED)},
                    "finished_ts": {"$gte": time.time() - 600},
                },
                {"log": 0},
            )
            .sort("finished_ts", -1)
            .limit(10)
        ]
        return JSONResponse(
            {
                "running": running,
                "scheduled": scheduled,
                "recent": recent,
                "now": time.time(),
            },
            headers=_NO_STORE,
        )

    @app.get(f"{base}/{{job_id}}", include_in_schema=False)
    def jobs_get(request: Request, job_id: str, since: int = 0):
        _, job = _owned(request, job_id)
        out = store.public(job, with_log=True, since=max(0, int(since or 0)))
        out["params"] = job.get("params") or {}
        out["now"] = time.time()
        if job.get("status") == "queued":
            col = store.collection()
            out["queue_ahead"] = col.count_documents(
                {
                    "service": job["service"],
                    "status": "queued",
                    "queued_ts": {"$lt": job.get("queued_ts") or time.time()},
                }
            )
        return JSONResponse(out, headers=_NO_STORE)

    @app.post(f"{base}/{{job_id}}/cancel", include_in_schema=False)
    def jobs_cancel(request: Request, job_id: str):
        _, job = _owned(request, job_id)
        col = store.collection()
        status = job.get("status")
        if status in ("scheduled", "queued"):
            # 아직 프로세스가 없다 — 바로 취소
            if store.finish(
                job_id,
                "cancelled",
                only_from=("scheduled", "queued"),
                stage="취소됨",
                cancel_requested=True,
            ):
                store.append_log(
                    job_id,
                    [
                        {
                            "t": time.time(),
                            "text": "실행 전에 취소했습니다.",
                            "level": "warn",
                        }
                    ],
                )
                return {"ok": True, "status": "cancelled"}
            job = store.get(job_id) or job
            status = job.get("status")
        if status in store.RUNNING:
            col.update_one(
                {"_id": job_id, "status": {"$in": list(store.RUNNING)}},
                {"$set": {"cancel_requested": True, "cancel_ts": time.time()}},
            )
            store.append_log(
                job_id,
                [
                    {
                        "t": time.time(),
                        "text": "중단 요청 — 프로세스를 정리하는 중입니다…",
                        "level": "warn",
                    }
                ],
            )
            return {"ok": True, "status": "cancelling"}
        raise HTTPException(409, "이미 끝난 작업입니다.")

    @app.post(f"{base}/{{job_id}}/retry", include_in_schema=False)
    async def jobs_retry(request: Request, job_id: str):
        user, job = _owned(request, job_id)
        if job.get("status") not in store.FINISHED:
            raise HTTPException(409, "끝난 작업만 다시 실행할 수 있습니다.")
        src = store.input_path(job)
        if job.get("input") and not (src and os.path.exists(src)):
            raise HTTPException(
                410,
                "입력 파일이 보관 기간이 지나 삭제되었습니다. 새로 분석을 시작해 주세요.",
            )
        try:
            body = await request.json()
        except Exception:
            body = {}
        scheduled = parse_schedule((body or {}).get("scheduled_at"))
        new = await asyncio.to_thread(
            store.create,
            service=job["service"],
            kind=job["kind"],
            kind_label=job.get("kind_label") or job["kind"],
            user={"uid": job["uid"], "name": job.get("user_name") or user.get("name")},
            title=job.get("title") or "",
            params=job.get("params") or {},
            filename=(job.get("input") or {}).get("filename"),
            source_input=src if job.get("input") else None,
            scheduled_ts=scheduled,
            retry_of=job_id,
        )
        return JSONResponse(store.public(new), headers=_NO_STORE)

    @app.patch(f"{base}/{{job_id}}", include_in_schema=False)
    async def jobs_reschedule(request: Request, job_id: str):
        """예약 작업의 시각 변경, 또는 run_now=true 로 지금 바로 대기열에 넣기."""
        _, job = _owned(request, job_id)
        if job.get("status") != "scheduled":
            raise HTTPException(409, "예약된 작업만 바꿀 수 있습니다.")
        body = await request.json()
        col = store.collection()
        if body.get("run_now"):
            col.update_one(
                {"_id": job_id, "status": "scheduled"},
                {
                    "$set": {
                        "status": "queued",
                        "queued_ts": time.time(),
                        "stage": "대기 중",
                        "scheduled_ts": None,
                    }
                },
            )
        else:
            ts = parse_schedule(body.get("scheduled_at"))
            if not ts:
                raise HTTPException(400, "예약 시각을 입력해 주세요.")
            col.update_one(
                {"_id": job_id, "status": "scheduled"}, {"$set": {"scheduled_ts": ts}}
            )
        return JSONResponse(store.public(store.get(job_id)), headers=_NO_STORE)

    @app.delete(f"{base}/{{job_id}}", include_in_schema=False)
    def jobs_delete(request: Request, job_id: str):
        """끝난 작업 기록 삭제(결과 프로젝트는 그대로 둔다)."""
        _, job = _owned(request, job_id)
        if job.get("status") not in store.FINISHED:
            raise HTTPException(409, "실행 중이거나 예약된 작업은 먼저 중단해 주세요.")
        store.collection().delete_one({"_id": job_id})
        store.remove_files(job_id)
        return {"ok": True}


def status_compat(uid: str, job_id: str) -> dict:
    """예전 /api/projects/analyze/{pid}/status 응답 모양(running|done|error)."""
    job = store.get(job_id, {"log": 0})
    if not job or job.get("uid") != uid:
        return {"status": "unknown", "project_id": None, "error": None}
    status = job.get("status")
    mapped = {
        "done": "done",
        "error": "error",
        "cancelled": "error",
        "interrupted": "error",
    }.get(status, "running")
    error = job.get("error")
    if status == "cancelled":
        error = error or "작업이 중단되었습니다."
    return {
        "status": mapped,
        "job_status": status,
        "project_id": (job.get("result") or {}).get("project_id"),
        "error": error,
    }
