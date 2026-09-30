"""프로젝트별 AI 해석 작업: DB 상태 공유, 완료 결과 영구 보관."""

import asyncio
import time
import uuid
from datetime import datetime, timezone

from app.db import network_ai_jobs_db, user_logs_db
from app.services import network_ai, project_store
from system.llm import LLMError
from system.logging.user_log import insert_log


def _now():
    return datetime.now(timezone.utc).isoformat()


def _job_out(doc):
    return {
        key: doc.get(key)
        for key in (
            "id",
            "project_id",
            "title",
            "mode",
            "tag",
            "status",
            "stage",
            "error",
            "result_id",
            "prompt",
            "created_at",
            "updated_at",
        )
    }


def _expire_stale():
    # 작업을 실행하던 서버가 재시작한 경우 무한 로딩으로 남겨두지 않는다.
    network_ai_jobs_db.update_many(
        {"status": "running", "heartbeat_at": {"$lt": time.time() - 75}},
        {
            "$set": {
                "status": "error",
                "stage": "작업 중단",
                "error": "서버가 재시작되어 분석이 중단되었습니다. 다시 분석해주세요.",
                "updated_at": _now(),
            }
        },
    )


def get_job(uid, project_id, job_id):
    _expire_stale()
    doc = network_ai_jobs_db.find_one(
        {"_id": job_id, "uid": uid, "project_id": project_id}
    )
    if not doc:
        raise project_store.NotFound("AI 분석 작업을 찾을 수 없습니다.")
    return _job_out({**doc, "id": doc["_id"]})


def active_jobs(uid):
    _expire_stale()
    docs = network_ai_jobs_db.find({"uid": uid, "status": "running"}).sort(
        "created_at", -1
    )
    return [_job_out({**doc, "id": doc["_id"]}) for doc in docs]


def _stage(job_id, name, prompt=None):
    fields = {"stage": name, "updated_at": _now(), "heartbeat_at": time.time()}
    if prompt is not None:
        fields["prompt"] = prompt
    network_ai_jobs_db.update_one({"_id": job_id}, {"$set": fields})


async def _heartbeat(job_id):
    while True:
        await asyncio.sleep(10)
        await asyncio.to_thread(
            network_ai_jobs_db.update_one,
            {"_id": job_id, "status": "running"},
            {"$set": {"heartbeat_at": time.time(), "updated_at": _now()}},
        )


def _prepare(uid, project_id, payload, admin):
    mode, tag = payload["mode"], payload["tag"]
    word, other, community = (
        payload.get("word"),
        payload.get("other"),
        payload.get("community"),
    )
    graph = project_store.load_graph(uid, project_id, tag, admin)
    series = network_ai.period_series(uid, project_id, tag, mode, word, other, admin)
    profile = network_ai.build_profile(graph, mode, word, other, community, series)
    meta = project_store.get_project(uid, project_id, admin)
    settings = (meta.get("analysis_options") or {}).get("options", {})
    profile["measure"] = settings.get("measure", "알 수 없음")
    profile["cooccurrence_unit"] = settings.get("scope", "알 수 없음")
    if settings.get("scope") == "window":
        profile["window_size"] = settings.get("window")
    examples, note = network_ai.source_examples(
        uid, project_id, graph, mode, tag, word, other, community, admin
    )
    return profile, examples, note


async def _run(job_id, uid, project_id, payload, admin):
    profile = examples = note = None
    prompt_holder = {}
    heartbeat = asyncio.create_task(_heartbeat(job_id))
    try:
        _stage(job_id, "전체 그래프와 기간별 지표를 계산하고 있어요")
        profile, examples, note = await asyncio.to_thread(
            _prepare, uid, project_id, payload, admin
        )
        _stage(
            job_id, f"근거 행 {len(examples)}개를 확인하고 AI 해석을 준비하고 있어요"
        )

        def on_prompt(prompt):
            prompt_holder.update(prompt)
            _stage(job_id, "AI가 연결 구조와 원문 맥락을 해석하고 있어요", prompt)

        try:
            interpretation = await network_ai.interpret(
                uid, profile, examples, note, on_prompt
            )
        except (LLMError, ValueError) as exc:
            interpretation = {
                "report": "",
                "error": str(exc),
                "model": None,
                "cost_usd": 0,
                "llm": None,
                "prompt": prompt_holder or None,
            }

        _stage(job_id, "해석 결과를 프로젝트에 저장하고 있어요")
        job = network_ai_jobs_db.find_one({"_id": job_id})
        saved = {
            "id": job_id,
            "mode": payload["mode"],
            "tag": payload["tag"],
            "title": job["title"],
            "created_at": _now(),
            "selection": payload,
            "profile": profile,
            "examples": examples,
            "evidence_note": note,
            **interpretation,
        }
        await asyncio.to_thread(
            project_store.save_ai_report, uid, project_id, saved, admin
        )
        try:
            insert_log(
                user_logs_db,
                uid,
                "network.ai_analysis",
                "network",
                target={"type": "project", "id": project_id},
                metadata={
                    "mode": payload["mode"],
                    "report_id": job_id,
                    "has_ai": bool(saved.get("report")),
                },
            )
        except Exception:
            pass
        network_ai_jobs_db.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "done",
                    "stage": "완료 · 보고서에 저장됨",
                    "result_id": job_id,
                    "updated_at": _now(),
                }
            },
        )
    except Exception as exc:
        network_ai_jobs_db.update_one(
            {"_id": job_id},
            {
                "$set": {
                    "status": "error",
                    "stage": "분석 실패",
                    "error": str(exc),
                    "updated_at": _now(),
                }
            },
        )
    finally:
        heartbeat.cancel()


def start_job(uid, project_id, payload, admin=False):
    mode = payload["mode"]
    label = {
        "overview": "전체 네트워크",
        "word": "단어",
        "pair": "단어쌍",
        "community": "커뮤니티",
    }[mode]
    subject = (
        {
            "word": payload.get("word"),
            "pair": f"{payload.get('word')} · {payload.get('other')}",
            "community": f"{payload.get('community')}",
        }.get(mode)
        or ""
    ).strip()
    title = (subject + " · " if subject else "") + label + " AI 분석"
    now = _now()
    job_id = uuid.uuid4().hex
    network_ai_jobs_db.insert_one(
        {
            "_id": job_id,
            "uid": uid,
            "project_id": project_id,
            "title": title,
            "mode": mode,
            "tag": payload["tag"],
            "status": "running",
            "stage": "준비 중",
            "prompt": None,
            "result_id": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
            "heartbeat_at": time.time(),
        }
    )
    asyncio.create_task(_run(job_id, uid, project_id, payload, admin))
    return job_id
