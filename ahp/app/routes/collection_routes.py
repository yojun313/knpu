"""수집 회차(collection) — 오프라인/온라인/실시간 배포 단위.

한 프로젝트에 여러 collection이 동시에 열려 있을 수 있다(오프라인 패널 진행 중에
온라인 링크도 함께 배포하는 식) — 그래서 project가 아니라 collection이 실제
"응답을 받는" 단위다. 같은 survey_id를 공유하는 여러 collection의 응답을
result_routes에서 합쳐 분석한다(PLAN.md 1절).
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.auth import current_uid, is_admin
from app.db import (
    collections_db,
    surveys_db,
    projects_db,
    respondents_db,
    responses_db,
    submissions_db,
    results_db,
    imports_db,
)
from app.services.codes import generate_code, hash_code, generate_access_token
from app.services.ahp_calc import derive_weights, IncompleteMatrixError

router = APIRouter()

MODES = {"offline", "online", "realtime"}
STATUS_LABELS = {"open": "진행 중", "closed": "종료됨"}


def _now():
    return datetime.now(timezone.utc)


async def _project_for_survey(survey_id: str) -> dict:
    survey = await surveys_db.find_one({"_id": survey_id})
    if not survey:
        raise HTTPException(404, "설문지를 찾을 수 없습니다")
    project = await projects_db.find_one({"_id": survey["project_id"]})
    if not project:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    return project


def _check_owner(project: dict, request: Request):
    uid = current_uid(request)
    if project.get("owner_uid") != uid and not is_admin(request):
        raise HTTPException(403, "이 프로젝트에 접근할 권한이 없습니다")


async def _get_collection_checked(collection_id: str, request: Request) -> dict:
    doc = await collections_db.find_one({"_id": collection_id})
    if not doc:
        raise HTTPException(404, "수집 회차를 찾을 수 없습니다")
    project = await _project_for_survey(doc["survey_id"])
    _check_owner(project, request)
    return doc


async def _get_project_checked(project_id: str, request: Request) -> dict:
    doc = await projects_db.find_one({"_id": project_id})
    if not doc:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    _check_owner(doc, request)
    return doc


async def _serialize_collection(doc: dict) -> dict:
    respondent_count = await respondents_db.count_documents(
        {"collection_id": doc["_id"]}
    )
    submitted_count = await respondents_db.count_documents(
        {"collection_id": doc["_id"], "status": "submitted"}
    )
    survey = await surveys_db.find_one({"_id": doc["survey_id"]}, {"project_id": 1})
    return {
        "id": doc["_id"],
        "project_id": survey["project_id"] if survey else None,
        "survey_id": doc["survey_id"],
        "survey_version": doc["survey_version"],
        "mode": doc["mode"],
        "label": doc.get("label", ""),
        "status": doc.get("status", "open"),
        "status_label": STATUS_LABELS.get(doc.get("status", "open"), doc.get("status")),
        "round": doc.get("round", 1),
        "access_token": doc.get("access_token"),
        "respondent_count": respondent_count,
        "submitted_count": submitted_count,
        "opened_at": doc.get("opened_at"),
        "closed_at": doc.get("closed_at"),
    }


@router.post("/api/collections")
async def create_collection(request: Request):
    body = await request.json()
    project_id = body.get("project_id")
    mode = body.get("mode")
    if mode not in MODES:
        raise HTTPException(400, f"mode는 {sorted(MODES)} 중 하나여야 합니다")

    project = await _get_project_checked(project_id, request)
    survey = await surveys_db.find_one(
        {"project_id": project_id, "status": "published"}, sort=[("version", -1)]
    )
    if not survey:
        raise HTTPException(400, "설문지를 먼저 발행해 주세요")

    doc = {
        "_id": uuid.uuid4().hex,
        "survey_id": survey["_id"],
        "survey_version": survey["version"],
        "mode": mode,
        "label": (body.get("label") or "").strip() or f"{mode} 수집",
        "status": "open",
        "round": 1,
        "access_token": None if mode == "offline" else generate_access_token(),
        "opened_at": _now(),
        "closed_at": None,
    }
    await collections_db.insert_one(doc)

    # 배포 시작 = 방법론 설정 잠금(PLAN.md 11) — 이후엔 새 collection으로만 바꿀 수 있다.
    await projects_db.update_one(
        {"_id": project_id}, {"$set": {"settings_locked": True, "updated_at": _now()}}
    )

    return await _serialize_collection(doc)


@router.get("/api/projects/{project_id}/collections")
async def list_collections(project_id: str, request: Request):
    await _get_project_checked(project_id, request)
    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    docs = (
        [
            d
            async for d in collections_db.find({"survey_id": {"$in": survey_ids}}).sort(
                "opened_at", -1
            )
        ]
        if survey_ids
        else []
    )
    return [await _serialize_collection(d) for d in docs]


@router.get("/api/collections/{collection_id}")
async def get_collection(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    return await _serialize_collection(doc)


@router.post("/api/collections/{collection_id}/close")
async def close_collection(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    await collections_db.update_one(
        {"_id": doc["_id"]}, {"$set": {"status": "closed", "closed_at": _now()}}
    )
    return {"status": "closed"}


@router.post("/api/collections/{collection_id}/reopen")
async def reopen_collection(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    await collections_db.update_one(
        {"_id": doc["_id"]}, {"$set": {"status": "open", "closed_at": None}}
    )
    return {"status": "open"}


@router.delete("/api/collections/{collection_id}")
async def delete_collection(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    cid = doc["_id"]
    await responses_db.delete_many({"collection_id": cid})
    await submissions_db.delete_many({"collection_id": cid})
    await results_db.delete_many({"collection_id": cid})
    await imports_db.delete_many({"collection_id": cid})
    await respondents_db.delete_many({"collection_id": cid})
    await collections_db.delete_one({"_id": cid})
    return {"status": "deleted", "id": cid}


@router.post("/api/collections/{collection_id}/codes")
async def issue_codes(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    if doc["mode"] == "offline":
        raise HTTPException(
            400, "오프라인 수집은 접속 코드가 필요 없습니다 (관리자가 직접 입력)"
        )

    body = await request.json()
    count = int(body.get("count", 1))
    if not (1 <= count <= 500):
        raise HTTPException(400, "한 번에 1~500개까지 발급할 수 있습니다")

    issued = []
    for i in range(count):
        code = generate_code()
        rid = uuid.uuid4().hex
        label = f"참여자 {chr(65 + (i % 26))}-{i + 1}"
        await respondents_db.insert_one(
            {
                "_id": rid,
                "collection_id": collection_id,
                "code_hash": hash_code(code),
                "label": label,
                "source": "web",
                "status": "not_started",
                "attributes": {},
                "consent_at": None,
                "created_at": _now(),
            }
        )
        issued.append({"respondent_id": rid, "label": label, "code": code})

    return {"issued": issued}


def respondent_progress_summary(matrices: list[dict], answers: dict) -> dict:
    """이 응답자의 전체 진행률과 "가장 문제 있는" CR 하나를 요약한다.
    콘솔에서는 매트릭스별 CR을 전부 늘어놓기보다, 한눈에 "이 사람 뭔가
    이상하다"를 알 수 있는 게 더 쓸모 있어서 최댓값(worst) 하나만 보여준다."""
    total_pairs = sum(
        len(m["child_uuids"]) * (len(m["child_uuids"]) - 1) // 2 for m in matrices
    )
    answered_pairs = sum(len(answers.get(m["matrix_id"], {})) for m in matrices)
    progress = round(100 * answered_pairs / total_pairs) if total_pairs else 100

    worst_cr = None
    all_complete = True
    for m in matrices:
        node_ids = m["child_uuids"]
        if len(node_ids) < 2:
            continue
        try:
            result = derive_weights(node_ids, answers.get(m["matrix_id"], {}))
            if result.cr is not None:
                worst_cr = result.cr if worst_cr is None else max(worst_cr, result.cr)
        except IncompleteMatrixError:
            all_complete = False

    return {
        "progress": progress,
        "worst_cr": worst_cr,
        "complete": all_complete and progress == 100,
    }


@router.get("/api/collections/{collection_id}/respondents")
async def list_respondents(collection_id: str, request: Request):
    collection = await _get_collection_checked(collection_id, request)
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    docs = [
        d
        async for d in respondents_db.find({"collection_id": collection_id}).sort(
            "created_at", 1
        )
    ]
    responses_by_rid = {
        r["respondent_id"]: r.get("answers", {})
        async for r in responses_db.find({"collection_id": collection_id})
    }
    return [
        {
            "id": d["_id"],
            "label": d["label"],
            "source": d.get("source", "web"),
            "status": d.get("status", "not_started"),
            "consent_at": d.get("consent_at"),
            "attributes": d.get("attributes", {}),
            **respondent_progress_summary(
                survey["matrices"], responses_by_rid.get(d["_id"], {})
            ),
        }
        for d in docs
    ]


@router.post("/api/collections/{collection_id}/advance-round")
async def advance_round(collection_id: str, request: Request):
    """델파이 다음 라운드 시작 — 같은 collection 안에서 round만 증가시킨다
    (새 collection을 만들지 않는다. round는 제출 스냅샷을 구분하는 값일 뿐이고,
    응답자·설문지·링크는 그대로 이어진다)."""
    doc = await _get_collection_checked(collection_id, request)
    new_round = doc.get("round", 1) + 1
    await collections_db.update_one({"_id": doc["_id"]}, {"$set": {"round": new_round}})
    await respondents_db.update_many(
        {"collection_id": collection_id, "status": "submitted"},
        {"$set": {"status": "in_progress"}},
    )
    from app.services.hub import hub

    await hub.publish(collection_id, "round.advanced", {"round": new_round})
    return {"round": new_round}
