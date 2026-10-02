"""분석 작업 저장소 — systems.analysis_jobs 컬렉션과 작업별 파일 폴더.

작업 하나 = 문서 하나. 어느 브라우저·기기에서 들어와도 같은 목록과 진행 상황을 보도록
상태·진행 로그를 모두 DB에 둔다. 입력 CSV 는 작업 폴더(KNPU_JOBS_DIR, 기본 ~/.knpu_jobs)에
저장해 두고, 워커 프로세스가 그 파일을 읽어 분석한다(실패·중단 작업을 다시 실행할 때도 쓴다).

상태 흐름:
  scheduled ─(예약 시각)→ queued ─(러너가 집어감)→ starting → running → done | error
  어느 단계에서든 → cancelled(사용자 중단) · interrupted(서버 재시작/종료로 끊김)
"""

import os
import shutil
import socket
import time
import uuid

ACTIVE = ("scheduled", "queued", "starting", "running", "cancelling")
RUNNING = ("starting", "running", "cancelling")
FINISHED = ("done", "error", "cancelled", "interrupted")

LOG_LIMIT = 1000  # 문서에 남기는 진행 로그 줄 수(오래된 줄부터 버린다)
HOST = socket.gethostname()

JOBS_DIR = os.path.expanduser(os.getenv("KNPU_JOBS_DIR") or "~/.knpu_jobs")


def collection():
    from system.db import systems_db

    return systems_db["analysis_jobs"]


_indexed = False


def ensure_indexes() -> None:
    global _indexed
    if _indexed:
        return
    col = collection()
    col.create_index([("uid", 1), ("created_ts", -1)])
    col.create_index([("service", 1), ("status", 1)])
    _indexed = True


def job_dir(job_id: str) -> str:
    return os.path.join(JOBS_DIR, job_id)


def input_path(job: dict) -> str | None:
    inp = job.get("input") or {}
    return (
        os.path.join(job_dir(job["_id"]), inp["stored"]) if inp.get("stored") else None
    )


def new_id() -> str:
    return uuid.uuid4().hex


def create(
    *,
    service: str,
    kind: str,
    kind_label: str,
    user: dict,
    title: str,
    params: dict,
    content: bytes | None = None,
    filename: str | None = None,
    scheduled_ts: float | None = None,
    retry_of: str | None = None,
    source_input: str | None = None,
) -> dict:
    """작업 문서를 만들고 입력 파일을 작업 폴더에 저장한다."""
    ensure_indexes()
    job_id = new_id()
    folder = job_dir(job_id)
    os.makedirs(folder, exist_ok=True)
    inp = None
    if content is not None or source_input:
        stored = "input" + (os.path.splitext(filename or "")[1] or ".csv")
        dest = os.path.join(folder, stored)
        if source_input:
            shutil.copyfile(source_input, dest)
        else:
            with open(dest, "wb") as f:
                f.write(content)
        inp = {
            "filename": filename,
            "stored": stored,
            "size": os.path.getsize(dest),
        }
    now = time.time()
    scheduled = bool(scheduled_ts and scheduled_ts > now + 5)
    doc = {
        "_id": job_id,
        "service": service,
        "kind": kind,
        "kind_label": kind_label,
        "uid": user["uid"],
        "user_name": user.get("name"),
        "title": title,
        "params": params,
        "input": inp,
        "status": "scheduled" if scheduled else "queued",
        "stage": "예약됨" if scheduled else "대기 중",
        "progress": None,
        "log": [],
        "log_seq": 0,
        "created_ts": now,
        "scheduled_ts": scheduled_ts if scheduled else None,
        "queued_ts": None if scheduled else now,
        "started_ts": None,
        "finished_ts": None,
        "heartbeat_ts": None,
        "result": None,
        "error": None,
        "cancel_requested": False,
        "host": None,
        "pgid": None,
        "retry_of": retry_of,
    }
    collection().insert_one(doc)
    return doc


def get(job_id: str, projection: dict | None = None) -> dict | None:
    return collection().find_one({"_id": job_id}, projection)


def append_log(job_id: str, lines: list[dict], extra: dict | None = None) -> None:
    """로그 줄을 붙이고(일련번호 n 부여) 단계·진행률 같은 필드를 함께 갱신한다."""
    col = collection()
    update: dict = {"$set": dict(extra or {})}
    if lines:
        cur = col.find_one_and_update(
            {"_id": job_id},
            {"$inc": {"log_seq": len(lines)}},
            projection={"log_seq": 1},
        )
        start = (cur or {}).get("log_seq") or 0
        for i, line in enumerate(lines):
            line["n"] = start + i + 1
        update["$push"] = {"log": {"$each": lines, "$slice": -LOG_LIMIT}}
    if not update["$set"]:
        del update["$set"]
    if update:
        col.update_one({"_id": job_id}, update)


def finish(job_id: str, status: str, *, only_from=None, **fields) -> bool:
    """최종 상태로 바꾼다. only_from 이 있으면 그 상태들일 때만 바꾼다(경쟁 방지)."""
    q: dict = {"_id": job_id}
    if only_from:
        q["status"] = {"$in": list(only_from)}
    fields.setdefault("finished_ts", time.time())
    res = collection().update_one(q, {"$set": {"status": status, **fields}})
    return res.modified_count > 0


def remove_files(job_id: str) -> None:
    shutil.rmtree(job_dir(job_id), ignore_errors=True)


def remove_input(job: dict) -> None:
    path = input_path(job)
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def public(job: dict, *, with_log: bool = False, since: int = 0) -> dict:
    """브라우저로 내보낼 모양. 입력 파일 경로 같은 서버 내부 정보는 뺀다."""
    out = {
        "id": job["_id"],
        "service": job.get("service"),
        "kind": job.get("kind"),
        "kind_label": job.get("kind_label"),
        "title": job.get("title"),
        "user_name": job.get("user_name"),
        "status": job.get("status"),
        "stage": job.get("stage"),
        "progress": job.get("progress"),
        "created_ts": job.get("created_ts"),
        "scheduled_ts": job.get("scheduled_ts"),
        "queued_ts": job.get("queued_ts"),
        "started_ts": job.get("started_ts"),
        "finished_ts": job.get("finished_ts"),
        "heartbeat_ts": job.get("heartbeat_ts"),
        "result": job.get("result"),
        "error": job.get("error"),
        "cancel_requested": bool(job.get("cancel_requested")),
        "retry_of": job.get("retry_of"),
        "input": {
            "filename": (job.get("input") or {}).get("filename"),
            "size": (job.get("input") or {}).get("size"),
            "available": bool(input_path(job) and os.path.exists(input_path(job))),
        }
        if job.get("input")
        else None,
        "summary": job.get("summary"),
        "log_seq": job.get("log_seq") or 0,
    }
    if with_log:
        out["log"] = [
            {k: v for k, v in line.items() if k in ("n", "t", "text", "level")}
            for line in (job.get("log") or [])
            if (line.get("n") or 0) > since
        ]
    return out


def gc(max_age_days: int = 14) -> None:
    """끝난 지 오래된 작업 폴더(입력 파일)를 지운다. 기록 자체는 남긴다."""
    if not os.path.isdir(JOBS_DIR):
        return
    cutoff = time.time() - max_age_days * 86400
    for name in os.listdir(JOBS_DIR):
        path = os.path.join(JOBS_DIR, name)
        try:
            if os.path.getmtime(path) > cutoff:
                continue
            job = get(name, {"status": 1})
            if job is None or job.get("status") in FINISHED:
                shutil.rmtree(path, ignore_errors=True)
        except OSError:
            continue
