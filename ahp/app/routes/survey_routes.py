"""설문지(survey) — 계층에서 자동 생성된 문항(matrices), 안내문, 노드별 설명.

계층 설계(project_routes)와 설문지 준비(여기)를 의도적으로 분리했다. 계층의
name/order는 트리 구조를 다루는 값이고, 여기서 다루는 node_descriptions는
"응답자에게 실제로 보여줄 설명 문구"다 — 연구자가 설계 단계에서 대충 적어둔
메모와, 설문 단계에서 다듬은 안내문이 같은 값일 필요가 없어서 따로 둔다.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.auth import current_uid, is_admin
from app.db import surveys_db, hierarchies_db, collections_db, responses_db, projects_db
from app.services.survey_service import (
    generate_matrices,
    diff_matrices,
    diff_has_impact,
    prune_answers,
)
from app.services.hub import hub

router = APIRouter()

DEFAULT_CONSENT_TEXT = (
    "이 설문은 연구 목적으로만 사용되며, 응답 내용은 통계적으로만 처리되어 "
    "개인을 식별할 수 있는 형태로 공개되지 않습니다. 참여는 자발적이며 언제든 "
    "중단할 수 있습니다."
)


def _now():
    return datetime.now(timezone.utc)


async def _get_project_checked(project_id: str, request: Request):
    doc = await projects_db.find_one({"_id": project_id})
    if not doc:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    uid = current_uid(request)
    if doc.get("owner_uid") != uid and not is_admin(request):
        raise HTTPException(403, "이 프로젝트에 접근할 권한이 없습니다")
    return doc


def _serialize_survey(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "project_id": doc["project_id"],
        "hierarchy_version": doc["hierarchy_version"],
        "version": doc["version"],
        "title": doc.get("title", ""),
        "intro_text": doc.get("intro_text", ""),
        "consent_text": doc.get("consent_text", DEFAULT_CONSENT_TEXT),
        "node_descriptions": doc.get("node_descriptions", {}),
        "matrices": doc.get("matrices", []),
        "status": doc.get("status", "draft"),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


async def _latest_hierarchy(project_id: str) -> dict:
    h = await hierarchies_db.find_one(
        {"project_id": project_id}, sort=[("version", -1)]
    )
    if not h:
        raise HTTPException(404, "계층을 먼저 설계해 주세요")
    return h


async def _ensure_survey(project_doc: dict) -> dict:
    """이 프로젝트의 최신 설문지를 반환한다. 아직 없으면 최신 계층에서 v1을 만든다."""
    project_id = project_doc["_id"]
    existing = await surveys_db.find_one(
        {"project_id": project_id}, sort=[("version", -1)]
    )
    if existing:
        return existing

    hierarchy = await _latest_hierarchy(project_id)
    alt_on = project_doc.get("settings", {}).get("alt_layer") == "on"
    matrices = generate_matrices(
        hierarchy["nodes"], hierarchy.get("alternatives", []), alt_on
    )
    node_descriptions = {
        n["uuid"]: n.get("description", "")
        for n in hierarchy["nodes"]
        if n.get("description")
    }
    doc = {
        "_id": uuid.uuid4().hex,
        "project_id": project_id,
        "hierarchy_version": hierarchy["version"],
        "version": 1,
        "title": project_doc["title"],
        "intro_text": "",
        "consent_text": DEFAULT_CONSENT_TEXT,
        "node_descriptions": node_descriptions,
        "matrices": matrices,
        "status": "draft",
        "created_at": _now(),
        "updated_at": _now(),
    }
    await surveys_db.insert_one(doc)
    return doc


@router.get("/api/projects/{project_id}/survey")
async def get_survey(project_id: str, request: Request):
    project = await _get_project_checked(project_id, request)
    doc = await _ensure_survey(project)
    return _serialize_survey(doc)


@router.put("/api/projects/{project_id}/survey")
async def update_survey(project_id: str, request: Request):
    """구조를 바꾸지 않는 편집(문구·설명·안내문) — 버전을 올리지 않는다."""
    project = await _get_project_checked(project_id, request)
    doc = await _ensure_survey(project)
    body = await request.json()

    patch = {}
    if "title" in body:
        patch["title"] = (body["title"] or "").strip() or doc["title"]
    if "intro_text" in body:
        patch["intro_text"] = body["intro_text"] or ""
    if "consent_text" in body:
        patch["consent_text"] = body["consent_text"] or DEFAULT_CONSENT_TEXT
    if "node_descriptions" in body and isinstance(body["node_descriptions"], dict):
        patch["node_descriptions"] = body["node_descriptions"]
    if "matrix_questions" in body and isinstance(body["matrix_questions"], dict):
        matrices = list(doc["matrices"])
        by_id = {m["matrix_id"]: m for m in matrices}
        for mid, text in body["matrix_questions"].items():
            if mid in by_id and text:
                by_id[mid]["question_text"] = text
        patch["matrices"] = matrices

    if not patch:
        raise HTTPException(400, "변경할 내용이 없습니다")
    patch["updated_at"] = _now()
    await surveys_db.update_one({"_id": doc["_id"]}, {"$set": patch})
    updated = await surveys_db.find_one({"_id": doc["_id"]})

    # 문구·설명만 바뀐 경우도 실시간 collection이 열려 있으면 그 자리에서
    # 응답자 화면에 반영한다(PLAN.md 7.3) — 전체 스냅샷을 그대로 보내는 게
    # 부분 diff보다 단순하고, 설문지 크기가 작아서 비용도 무시할 만하다.
    open_realtime = collections_db.find(
        {
            "survey_id": {
                "$in": [
                    s["_id"]
                    async for s in surveys_db.find(
                        {"project_id": project_id}, {"_id": 1}
                    )
                ]
            },
            "mode": "realtime",
            "status": "open",
        }
    )
    async for coll in open_realtime:
        await hub.publish(
            coll["_id"],
            "survey.patch",
            {
                "node_descriptions": updated.get("node_descriptions", {}),
                "matrices": updated.get("matrices", []),
            },
        )

    return _serialize_survey(updated)


@router.post("/api/projects/{project_id}/survey/resync")
async def resync_survey(project_id: str, request: Request):
    """최신 계층에서 matrices를 다시 뽑아 설문지에 반영한다.

    구조가 실제로 바뀐 경우(형제 추가/삭제/이동)에만 이 프로젝트의 모든 collection에
    걸린 기존 응답을 정리한다(PLAN.md 4.4) — 이름·설명만 바뀐 경우는 응답을 건드리지
    않는다. 정리 전 원본은 손대지 않고 그대로 두고, 정리된 결과만 새로 저장한다
    (완전한 이력 보존은 향후 change-log 컬렉션 과제로 남겨둔다 — 지금은 최소한
    "몇 건이 어떻게 정리됐는지"를 응답으로 알려준다).
    """
    project = await _get_project_checked(project_id, request)
    current = await _ensure_survey(project)
    hierarchy = await _latest_hierarchy(project_id)

    if hierarchy["version"] == current["hierarchy_version"]:
        return {"changed": False, "message": "계층이 그대로라 변경할 내용이 없습니다"}

    alt_on = project.get("settings", {}).get("alt_layer") == "on"
    new_matrices = generate_matrices(
        hierarchy["nodes"], hierarchy.get("alternatives", []), alt_on
    )
    diff = diff_matrices(current["matrices"], new_matrices)
    impact = diff_has_impact(diff)

    new_descriptions = dict(current.get("node_descriptions", {}))
    for n in hierarchy["nodes"]:
        if n["uuid"] not in new_descriptions and n.get("description"):
            new_descriptions[n["uuid"]] = n["description"]

    next_version = current["version"] + 1
    new_doc = {
        "_id": uuid.uuid4().hex,
        "project_id": project_id,
        "hierarchy_version": hierarchy["version"],
        "version": next_version,
        "title": current["title"],
        "intro_text": current.get("intro_text", ""),
        "consent_text": current.get("consent_text", DEFAULT_CONSENT_TEXT),
        "node_descriptions": new_descriptions,
        "matrices": new_matrices,
        "status": current.get("status", "draft"),
        "created_at": _now(),
        "updated_at": _now(),
    }
    await surveys_db.insert_one(new_doc)

    pruned_count = 0
    if impact:
        old_survey_ids = [
            s["_id"]
            async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
        ]
        collection_ids = [
            c["_id"]
            async for c in collections_db.find(
                {"survey_id": {"$in": old_survey_ids}}, {"_id": 1}
            )
        ]
        if collection_ids:
            async for resp in responses_db.find(
                {"collection_id": {"$in": collection_ids}}
            ):
                pruned_answers, changed = prune_answers(resp.get("answers", {}), diff)
                if changed:
                    pruned_count += 1
                    await responses_db.update_one(
                        {"_id": resp["_id"]},
                        {"$set": {"answers": pruned_answers, "updated_at": _now()}},
                    )

    return {
        "changed": True,
        "impact": impact,
        "version": next_version,
        "diff": diff,
        "pruned_responses": pruned_count,
    }


@router.get("/api/surveys/{survey_id}/print-data")
async def survey_print_data(survey_id: str, request: Request):
    """인쇄 미리보기 전용 — survey_id로 직접 조회한다(특정 과거 버전을 인쇄할 수도
    있어서 "프로젝트의 최신 설문지"가 아니라 정확히 이 버전을 찾는다)."""
    survey = await surveys_db.find_one({"_id": survey_id})
    if not survey:
        raise HTTPException(404, "설문지를 찾을 수 없습니다")
    project = await projects_db.find_one({"_id": survey["project_id"]})
    if not project:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    uid = current_uid(request)
    if project.get("owner_uid") != uid and not is_admin(request):
        raise HTTPException(403, "이 설문지에 접근할 권한이 없습니다")

    hierarchy = await hierarchies_db.find_one(
        {"project_id": survey["project_id"], "version": survey["hierarchy_version"]}
    )
    nodes_by_uuid = {n["uuid"]: n for n in hierarchy["nodes"]} if hierarchy else {}
    # 대안 비교 행렬의 child_uuids는 대안 uuid라, 이것도 같이 넣어야 인쇄물에서
    # 대안 이름이 uuid로 안 보이고 정상 표시된다.
    for a in (hierarchy or {}).get("alternatives", []):
        nodes_by_uuid[a["uuid"]] = a
    return {"survey": _serialize_survey(survey), "nodes": nodes_by_uuid}


@router.post("/api/projects/{project_id}/survey/publish")
async def publish_survey(project_id: str, request: Request):
    project = await _get_project_checked(project_id, request)
    doc = await _ensure_survey(project)
    if not doc.get("matrices"):
        raise HTTPException(400, "비교할 항목이 없습니다. 계층을 먼저 완성해 주세요")
    await surveys_db.update_one(
        {"_id": doc["_id"]}, {"$set": {"status": "published", "updated_at": _now()}}
    )
    await projects_db.update_one(
        {"_id": project_id}, {"$set": {"status": "active", "updated_at": _now()}}
    )
    return {"status": "published", "survey_id": doc["_id"]}
