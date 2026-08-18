"""프로젝트 CRUD, 프로젝트 설정(방법론 7종), 계층(hierarchy) 버전 관리."""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from app.auth import current_uid, current_user, is_admin
from app.db import (
    projects_db,
    hierarchies_db,
    surveys_db,
    collections_db,
    respondents_db,
    responses_db,
    submissions_db,
    results_db,
    imports_db,
)

router = APIRouter()

DEFAULT_SETTINGS = {
    "aggregation": "AIP",  # AIJ | AIP — 기본 AIP: 개인 CR을 응답 즉시 확보(PLAN.md 11)
    "weight_method": "eigen",  # eigen | geomean
    "alt_layer": "off",  # off | on
    "incomplete_policy": "block",  # block | allow_partial | harker
    "scale": 9,  # 9 | 5
    "cr_threshold": 0.1,
    "cr_action": "warn",  # warn | block
}

# 배포(수집 시작) 이후에는 방법론이 바뀌면 이미 받은 응답과 이후 응답의 계산
# 방식이 어긋나 결과가 오염된다(PLAN.md 11). 이 4개는 첫 collection이 열리는
# 순간부터 잠긴다.
LOCKED_AFTER_OPEN = {"aggregation", "weight_method", "alt_layer", "scale"}

STATUS_LABELS = {"draft": "설계 중", "active": "진행 중", "closed": "종료됨"}


def _now():
    return datetime.now(timezone.utc)


def _serialize_project(doc: dict) -> dict:
    return {
        "id": doc["_id"],
        "title": doc["title"],
        "description": doc.get("description", ""),
        "status": doc.get("status", "draft"),
        "status_label": STATUS_LABELS.get(
            doc.get("status", "draft"), doc.get("status")
        ),
        "owner_uid": doc.get("owner_uid"),
        "owner_name": doc.get("owner_name"),
        "settings": {**DEFAULT_SETTINGS, **doc.get("settings", {})},
        "settings_locked": doc.get("settings_locked", False),
        "created_at": doc.get("created_at"),
        "updated_at": doc.get("updated_at"),
    }


@router.get("/api/me")
async def api_me(request: Request):
    return JSONResponse(current_user(request))


@router.get("/api/projects")
async def list_projects(request: Request, all: bool = Query(False)):
    uid = current_uid(request)
    query = {} if (all and is_admin(request)) else {"owner_uid": uid}
    docs = [d async for d in projects_db.find(query).sort("updated_at", -1)]
    return [_serialize_project(d) for d in docs]


@router.post("/api/projects")
async def create_project(request: Request):
    body = await request.json()
    title = (body.get("title") or "").strip()
    if not title:
        raise HTTPException(400, "제목을 입력해 주세요")

    user = current_user(request)
    now = _now()
    doc = {
        "_id": uuid.uuid4().hex,
        "owner_uid": user["uid"],
        "owner_name": user.get("name"),
        "title": title,
        "description": (body.get("description") or "").strip(),
        "status": "draft",
        "settings": dict(DEFAULT_SETTINGS),
        "settings_locked": False,
        "created_at": now,
        "updated_at": now,
    }
    await projects_db.insert_one(doc)

    # 빈 계층(루트 하나)으로 시작 — 설계 화면이 바로 편집할 대상이 있게 한다.
    root_id = uuid.uuid4().hex
    await hierarchies_db.insert_one(
        {
            "_id": uuid.uuid4().hex,
            "project_id": doc["_id"],
            "version": 1,
            "nodes": [
                {
                    "uuid": root_id,
                    "parent_id": None,
                    "name": title,
                    "description": "",
                    "order": 0,
                    "level": 0,
                }
            ],
            "created_at": now,
        }
    )

    return _serialize_project(doc)


async def _get_project_or_404(project_id: str, request: Request) -> dict:
    doc = await projects_db.find_one({"_id": project_id})
    if not doc:
        raise HTTPException(404, "프로젝트를 찾을 수 없습니다")
    uid = current_uid(request)
    if doc.get("owner_uid") != uid and not is_admin(request):
        raise HTTPException(403, "이 프로젝트에 접근할 권한이 없습니다")
    return doc


@router.get("/api/projects/{project_id}")
async def get_project(project_id: str, request: Request):
    doc = await _get_project_or_404(project_id, request)
    return _serialize_project(doc)


@router.put("/api/projects/{project_id}")
async def update_project(project_id: str, request: Request):
    await _get_project_or_404(project_id, request)
    body = await request.json()
    patch = {}
    if "title" in body:
        title = (body["title"] or "").strip()
        if not title:
            raise HTTPException(400, "제목은 비울 수 없습니다")
        patch["title"] = title
    if "description" in body:
        patch["description"] = (body["description"] or "").strip()
    if "status" in body and body["status"] in STATUS_LABELS:
        patch["status"] = body["status"]
    if not patch:
        raise HTTPException(400, "변경할 내용이 없습니다")
    patch["updated_at"] = _now()
    await projects_db.update_one({"_id": project_id}, {"$set": patch})
    doc = await projects_db.find_one({"_id": project_id})
    return _serialize_project(doc)


@router.delete("/api/projects/{project_id}")
async def delete_project(project_id: str, request: Request):
    await _get_project_or_404(project_id, request)

    survey_ids = [
        s["_id"] async for s in surveys_db.find({"project_id": project_id}, {"_id": 1})
    ]
    collection_ids = (
        [
            c["_id"]
            async for c in collections_db.find(
                {"survey_id": {"$in": survey_ids}}, {"_id": 1}
            )
        ]
        if survey_ids
        else []
    )

    if collection_ids:
        await responses_db.delete_many({"collection_id": {"$in": collection_ids}})
        await submissions_db.delete_many({"collection_id": {"$in": collection_ids}})
        await results_db.delete_many({"collection_id": {"$in": collection_ids}})
        await imports_db.delete_many({"collection_id": {"$in": collection_ids}})
        await respondents_db.delete_many({"collection_id": {"$in": collection_ids}})
        await collections_db.delete_many({"_id": {"$in": collection_ids}})
    if survey_ids:
        await surveys_db.delete_many({"_id": {"$in": survey_ids}})
    await hierarchies_db.delete_many({"project_id": project_id})
    await projects_db.delete_one({"_id": project_id})

    return JSONResponse({"status": "deleted", "id": project_id})


# ── 프로젝트 설정(방법론 7종) ──────────────────────────────────────────────
@router.get("/api/projects/{project_id}/settings")
async def get_settings(project_id: str, request: Request):
    doc = await _get_project_or_404(project_id, request)
    return {
        "settings": {**DEFAULT_SETTINGS, **doc.get("settings", {})},
        "locked": doc.get("settings_locked", False),
        "locked_fields": sorted(LOCKED_AFTER_OPEN)
        if doc.get("settings_locked")
        else [],
    }


@router.put("/api/projects/{project_id}/settings")
async def update_settings(project_id: str, request: Request):
    doc = await _get_project_or_404(project_id, request)
    body = await request.json()

    locked = doc.get("settings_locked", False)
    current = {**DEFAULT_SETTINGS, **doc.get("settings", {})}
    new_settings = dict(current)

    for key in DEFAULT_SETTINGS:
        if key not in body:
            continue
        if locked and key in LOCKED_AFTER_OPEN and body[key] != current[key]:
            raise HTTPException(
                409,
                f"'{key}'는 이미 배포된 설문이 있어 변경할 수 없습니다. "
                "새 collection으로 다시 시작해 주세요.",
            )
        new_settings[key] = body[key]

    await projects_db.update_one(
        {"_id": project_id},
        {"$set": {"settings": new_settings, "updated_at": _now()}},
    )
    return {"settings": new_settings, "locked": locked}


# ── 계층(hierarchy) ─────────────────────────────────────────────────────
def _validate_and_normalize_nodes(nodes: list[dict]) -> list[dict]:
    if not nodes:
        raise HTTPException(400, "최소 한 개의 루트 노드가 필요합니다")

    seen_uuids = set()
    for n in nodes:
        if not n.get("uuid"):
            raise HTTPException(400, "노드에 uuid가 없습니다")
        if n["uuid"] in seen_uuids:
            raise HTTPException(400, f"중복된 노드 uuid: {n['uuid']}")
        seen_uuids.add(n["uuid"])

    by_id = {n["uuid"]: n for n in nodes}
    for n in nodes:
        pid = n.get("parent_id")
        if pid is not None and pid not in by_id:
            raise HTTPException(400, f"존재하지 않는 부모를 참조합니다: {pid}")

    # 순환 참조 감지(부모를 계속 따라 올라갔을 때 자기 자신으로 돌아오면 안 됨)
    for n in nodes:
        visited = set()
        cur = n.get("parent_id")
        while cur is not None:
            if cur in visited or cur == n["uuid"]:
                raise HTTPException(400, "계층에 순환 참조가 있습니다")
            visited.add(cur)
            cur = by_id[cur].get("parent_id")

    # 레벨(깊이) 계산
    def depth(node_id: str) -> int:
        d, cur = 0, by_id[node_id].get("parent_id")
        while cur is not None:
            d += 1
            cur = by_id[cur].get("parent_id")
        return d

    normalized = []
    for n in nodes:
        normalized.append(
            {
                "uuid": n["uuid"],
                "parent_id": n.get("parent_id"),
                "name": (n.get("name") or "").strip() or "(이름 없음)",
                "description": n.get("description", ""),
                "order": n.get("order", 0),
                "level": depth(n["uuid"]),
            }
        )
    return normalized


def _sibling_warnings(nodes: list[dict]) -> list[dict]:
    """PLAN.md 6.1: 한 부모의 자식이 7개를 넘으면 응답 피로 경고(설계 시점 힌트,
    저장을 막지는 않는다 — 21쌍(7개)부터 급증, 9개면 36쌍)."""
    from collections import defaultdict

    children = defaultdict(list)
    for n in nodes:
        if n["parent_id"] is not None:
            children[n["parent_id"]].append(n["uuid"])
    by_id = {n["uuid"]: n for n in nodes}
    warnings = []
    for parent_id, kids in children.items():
        if len(kids) > 7:
            pairs = len(kids) * (len(kids) - 1) // 2
            warnings.append(
                {
                    "parent_id": parent_id,
                    "parent_name": by_id.get(parent_id, {}).get("name", parent_id),
                    "child_count": len(kids),
                    "pair_count": pairs,
                    "message": f"'{by_id.get(parent_id, {}).get('name')}' 아래 {len(kids)}개 "
                    f"항목 → 쌍대비교 {pairs}개. 7개 이하를 권장합니다.",
                }
            )
    return warnings


@router.get("/api/projects/{project_id}/hierarchy")
async def get_hierarchy(project_id: str, request: Request):
    await _get_project_or_404(project_id, request)
    doc = await hierarchies_db.find_one(
        {"project_id": project_id}, sort=[("version", -1)]
    )
    if not doc:
        raise HTTPException(404, "계층을 찾을 수 없습니다")
    return {
        "version": doc["version"],
        "nodes": doc["nodes"],
        "warnings": _sibling_warnings(doc["nodes"]),
    }


@router.put("/api/projects/{project_id}/hierarchy")
async def put_hierarchy(project_id: str, request: Request):
    await _get_project_or_404(project_id, request)
    body = await request.json()
    nodes = _validate_and_normalize_nodes(body.get("nodes") or [])

    latest = await hierarchies_db.find_one(
        {"project_id": project_id}, sort=[("version", -1)]
    )
    next_version = (latest["version"] + 1) if latest else 1

    doc = {
        "_id": uuid.uuid4().hex,
        "project_id": project_id,
        "version": next_version,
        "nodes": nodes,
        "created_at": _now(),
    }
    await hierarchies_db.insert_one(doc)
    await projects_db.update_one({"_id": project_id}, {"$set": {"updated_at": _now()}})

    return {
        "version": next_version,
        "nodes": nodes,
        "warnings": _sibling_warnings(nodes),
    }
