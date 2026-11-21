"""구성원 본인의 작업 현황 도구 — 프로젝트 · 분석 작업 · 크롤링 DB · 서비스 상태 (읽기 전용).

본인 자료(프로젝트·작업)는 반드시 ctx.uid 로만 조회한다. 크롤링 DB 목록은 크롤러 화면에서도
구성원 모두에게 보이는 범위(이름·키워드·기간·건수·상태)만 돌려준다.
"""

import re
import socket
import time
from datetime import datetime, timezone

from ..registry import tool

M = ("member",)
_PROJECT_SERVICES = {
    "network": ("NETWORK", "network_projects_db"),
    "kemkim": ("KEMKIM", "kemkim_projects_db"),
    "statistics": ("STATISTICS", "statistics_projects_db"),
}
_JOB_STATUS = {
    "queued": "대기 중", "scheduled": "예약됨", "running": "실행 중", "done": "완료",
    "error": "실패", "failed": "실패", "cancelled": "중단됨", "canceled": "중단됨",
}  # fmt: skip


def _need_user(ctx) -> str:
    if not ctx.uid:
        raise ValueError("로그인한 구성원만 쓸 수 있는 도구입니다.")
    return ctx.uid


def _when(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return (
            datetime.fromtimestamp(v, timezone.utc)
            .astimezone()
            .strftime("%Y-%m-%d %H:%M")
        )
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d %H:%M")
    return str(v)[:16].replace("T", " ")


def _limit(v, default=15, cap=40) -> int:
    try:
        return max(1, min(cap, int(v or default)))
    except (TypeError, ValueError):
        return default


@tool(
    "my_projects",
    "지금 대화하는 구성원의 분석 프로젝트 목록(NETWORK·KEMKIM·STATISTICS): 이름·만든 날·자료 출처. '내 프로젝트 뭐 있지', '지난번 분석 어디 있지'에 쓴다",
    {
        "service": "(선택) network/kemkim/statistics",
        "query": "(선택) 프로젝트 이름 일부",
    },
    modes=M,
    label="내 프로젝트 확인 · {service}",
    cache_s=20,
    per_user=True,
)
def my_projects(ctx, service="", query=""):
    uid = _need_user(ctx)
    import system.db as db

    svc = str(service).strip().lower()
    if svc and svc not in _PROJECT_SERVICES:
        raise ValueError("service 는 network/kemkim/statistics 중 하나여야 합니다.")
    q = {"uid": uid}
    if str(query).strip():
        q["name"] = {"$regex": re.escape(str(query).strip()), "$options": "i"}
    out, counts = [], {}
    for key, (label, col_name) in _PROJECT_SERVICES.items():
        if svc and key != svc:
            continue
        col = getattr(db, col_name)
        counts[label] = col.count_documents(q)
        for d in (
            col.find(
                q,
                {
                    "name": 1,
                    "created_at": 1,
                    "updated_at": 1,
                    "source": 1,
                    "source_filename": 1,
                    "row_count": 1,
                    "table_count": 1,
                },
            )
            .sort("updated_at", -1)
            .limit(25)
        ):
            item = {
                "service": label,
                "name": d.get("name"),
                "created": _when(d.get("created_at")),
                "updated": _when(d.get("updated_at")),
            }
            for k in ("source", "source_filename", "row_count", "table_count"):
                if d.get(k) not in (None, ""):
                    item[k] = d[k]
            out.append(item)
    out.sort(key=lambda x: x.get("updated") or "", reverse=True)
    return {
        "count_by_service": counts,
        "count": sum(counts.values()),
        "projects": out[:40],
        "truncated": len(out) > 40,
    }


@tool(
    "my_jobs",
    "지금 대화하는 구성원의 분석·수집 작업 현황(대기·실행 중·완료·실패, 진행률, 오류 사유). '내 분석 끝났나', '왜 실패했지'에 쓴다",
    {
        "status": "(선택) running/queued/done/error 중 하나",
        "service": "(선택) 서비스 이름",
        "limit": "(선택) 개수(기본 15)",
    },
    modes=M,
    label="내 작업 현황 확인",
    cache_s=5,
    per_user=True,
)
def my_jobs(ctx, status="", service="", limit=""):
    uid = _need_user(ctx)
    from system.db import analysis_jobs_db

    q: dict = {"uid": uid}
    st = str(status).strip().lower()
    if st:
        q["status"] = {"$in": ["error", "failed"]} if st in ("error", "failed") else st
    if str(service).strip():
        q["service"] = str(service).strip().lower()
    fields = {
        k: 1
        for k in (
            "service",
            "kind_label",
            "title",
            "status",
            "stage",
            "progress",
            "created_ts",
            "started_ts",
            "finished_ts",
            "error",
        )
    }
    docs = list(
        analysis_jobs_db.find(q, fields).sort("created_ts", -1).limit(_limit(limit))
    )
    counts: dict = {}
    for d in (
        analysis_jobs_db.find({"uid": uid}, {"status": 1})
        .sort("created_ts", -1)
        .limit(300)
    ):
        label = _JOB_STATUS.get(d.get("status"), d.get("status") or "?")
        counts[label] = counts.get(label, 0) + 1
    jobs = []
    for d in docs:
        item = {
            "service": d.get("service"),
            "kind": d.get("kind_label"),
            "title": d.get("title"),
            "status": _JOB_STATUS.get(d.get("status"), d.get("status")),
            "stage": d.get("stage"),
            "progress": d.get("progress"),
            "created": _when(d.get("created_ts")),
            "finished": _when(d.get("finished_ts")),
        }
        if d.get("started_ts") and not d.get("finished_ts"):
            item["running_minutes"] = round(
                (time.time() - float(d["started_ts"])) / 60, 1
            )
        if d.get("error"):
            item["error"] = str(d["error"])[:300]
        jobs.append({k: v for k, v in item.items() if v not in (None, "")})
    return {"count_by_status": counts, "shown": len(jobs), "jobs": jobs}


@tool(
    "crawl_data",
    "크롤링 DB 목록(이름·플랫폼·키워드·기간·수집 건수·상태·요청자). '○○ 키워드 수집한 데이터 있나', '내 크롤링 끝났나'에 쓴다",
    {
        "query": "(선택) 키워드·DB 이름·요청자",
        "mine": "(선택) true 면 내가 요청한 것만",
        "status": "(선택) running/completed/stopped/error",
        "limit": "(선택) 개수(기본 15)",
    },
    modes=M,
    label="크롤링 DB 확인 · {query}",
    cache_s=15,
    per_user=True,
)
def crawl_data(ctx, query="", mine="", status="", limit=""):
    uid = _need_user(ctx)
    from system.db import crawlList_db

    q: dict = {}
    if str(mine).strip().lower() in ("1", "true", "yes", "y", "예", "내것", "mine"):
        q["userUid"] = uid
    if str(status).strip():
        q["status"] = str(status).strip().lower()
    if str(query).strip():
        rx = {"$regex": re.escape(str(query).strip()), "$options": "i"}
        q["$or"] = [{"keyword": rx}, {"name": rx}, {"requester": rx}]
    total = crawlList_db.count_documents(q)
    fields = {
        k: 1
        for k in (
            "name",
            "crawlObject",
            "keyword",
            "startDate",
            "endDate",
            "requester",
            "userUid",
            "stat",
            "status",
            "percent",
            "startTime",
            "endTime",
            "dbSize",
        )
    }
    items = []
    for d in crawlList_db.find(q, fields).sort("startTime", -1).limit(_limit(limit)):
        stat = d.get("stat") or {}
        items.append(
            {
                "name": d.get("name"),
                "platform": d.get("crawlObject"),
                "keyword": d.get("keyword"),
                "period": f"{d.get('startDate')}~{d.get('endDate')}",
                "status": d.get("status"),
                "percent": d.get("percent"),
                "articles": stat.get("article"),
                "comments": stat.get("cmt"),
                "replies": stat.get("reply"),
                "requester": d.get("requester"),
                "mine": d.get("userUid") == uid,
                "started": d.get("startTime"),
                "ended": d.get("endTime"),
            }
        )
    return {
        "count": total,
        "shown": len(items),
        "items": items,
    }  # 전체 건수는 코드가 센다


@tool(
    "service_status",
    "연구실 각 서비스가 지금 응답하는지(서버 포트 연결 확인). '크롤러 지금 되나', '사이트가 안 열린다'에 쓴다",
    {"service": "(선택) 서비스 키 예: crawler"},
    modes=M,
    label="서비스 상태 확인 · {service}",
    cache_s=15,
)
def service_status(ctx, service=""):
    from system import endpoints

    from .. import tools

    names = {s["key"]: s["name"] for s in tools.SERVICES}
    want = str(service).strip().lower()
    out = []
    for key in endpoints.service_names():
        if want and want not in (key, names.get(key, "").lower()):
            continue
        try:
            port = endpoints.port(key)
        except Exception:
            continue
        started = time.monotonic()
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                ok = True
        except OSError:
            ok = False
        item = {
            "service": key,
            "name": names.get(key, key),
            "up": ok,
            "url": endpoints.public_url(key),
        }
        if ok:
            item["connect_ms"] = round((time.monotonic() - started) * 1000)
        out.append(item)
    if not out:
        raise ValueError(
            f"없는 서비스입니다. 가능한 값: {', '.join(endpoints.service_names())}"
        )
    return {
        "checked": len(out),
        "down": [s["name"] for s in out if not s["up"]],
        "services": out,
        "note": "포트 연결만 확인한 결과입니다. 연결되지만 기능이 느리거나 오류가 나는 경우는 구분하지 못합니다.",
    }
