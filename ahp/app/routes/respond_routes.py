"""응답자용 공개 API — 로그인 없이 접근한다(AuthMiddleware의 extra_public_paths).

인증은 이 파일 안에서 직접 처리한다: 접속 코드로 응답자를 식별하면 짧은 수명의
응답자 전용 토큰(app.auth.create_respondent_token)을 발급하고, 이후 요청은
Authorization 헤더로 그 토큰을 검증한다.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from app.auth import create_respondent_token, current_respondent
from app.db import (
    collections_db,
    surveys_db,
    hierarchies_db,
    respondents_db,
    responses_db,
    submissions_db,
    projects_db,
)
from app.services.codes import hash_code
from app.services.ahp_calc import (
    to_stored_pair,
    pair_id,
    derive_weights,
    IncompleteMatrixError,
)
from app.services.hub import hub

router = APIRouter()


def _now():
    return datetime.now(timezone.utc)


async def _collection_by_token(token: str) -> dict:
    doc = await collections_db.find_one({"access_token": token})
    if not doc:
        raise HTTPException(404, "유효하지 않은 링크입니다")
    return doc


async def _survey_and_nodes(collection: dict):
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    hierarchy = await hierarchies_db.find_one(
        {"project_id": survey["project_id"], "version": survey["hierarchy_version"]}
    )
    nodes_by_id = {n["uuid"]: n for n in hierarchy["nodes"]}
    return survey, nodes_by_id


def _build_matrices_view(survey: dict, nodes_by_id: dict) -> list[dict]:
    out = []
    for m in survey["matrices"]:
        children = [
            {
                "uuid": cid,
                "name": nodes_by_id.get(cid, {}).get("name", cid),
                "description": survey.get("node_descriptions", {}).get(cid, ""),
            }
            for cid in m["child_uuids"]
        ]
        out.append(
            {
                "matrix_id": m["matrix_id"],
                "parent_name": nodes_by_id.get(m["parent_uuid"], {}).get("name", ""),
                "parent_description": survey.get("node_descriptions", {}).get(
                    m["parent_uuid"], ""
                ),
                "question_text": m["question_text"],
                "children": children,
                "pairs": [
                    {"uuid_a": m["child_uuids"][i], "uuid_b": m["child_uuids"][j]}
                    for i in range(len(m["child_uuids"]))
                    for j in range(i + 1, len(m["child_uuids"]))
                ],
            }
        )
    return out


@router.get("/api/respond/{token}")
async def respond_landing(token: str):
    collection = await _collection_by_token(token)
    survey, nodes_by_id = await _survey_and_nodes(collection)
    project = await projects_db.find_one({"_id": survey["project_id"]}, {"settings": 1})

    return {
        "collection": {
            "id": collection["_id"],
            "mode": collection["mode"],
            "status": collection.get("status", "open"),
            "label": collection.get("label"),
        },
        "survey": {
            "title": survey["title"],
            "intro_text": survey.get("intro_text", ""),
            "consent_text": survey.get("consent_text", ""),
            "scale": (project or {}).get("settings", {}).get("scale", 9),
            "cr_threshold": (project or {})
            .get("settings", {})
            .get("cr_threshold", 0.1),
            "cr_action": (project or {}).get("settings", {}).get("cr_action", "warn"),
            "matrices": _build_matrices_view(survey, nodes_by_id),
        },
    }


@router.post("/api/respond/{token}/verify")
async def verify_code(token: str, request: Request):
    collection = await _collection_by_token(token)
    if collection.get("status") != "open":
        raise HTTPException(410, "이 설문은 마감되었습니다")

    body = await request.json()
    code = (body.get("code") or "").strip()
    consent = bool(body.get("consent"))
    if not consent:
        raise HTTPException(400, "참여에 동의해야 계속할 수 있습니다")
    if not code:
        raise HTTPException(400, "접속 코드를 입력해 주세요")

    respondent = await respondents_db.find_one(
        {
            "collection_id": collection["_id"],
            "code_hash": hash_code(code),
        }
    )
    if not respondent:
        raise HTTPException(404, "코드를 확인할 수 없습니다. 다시 확인해 주세요")

    update = (
        {"status": "in_progress"} if respondent.get("status") == "not_started" else {}
    )
    if not respondent.get("consent_at"):
        update["consent_at"] = _now()
    if update:
        await respondents_db.update_one({"_id": respondent["_id"]}, {"$set": update})

    existing_resp = await responses_db.find_one(
        {"collection_id": collection["_id"], "respondent_id": respondent["_id"]}
    )
    if not existing_resp:
        await responses_db.insert_one(
            {
                "_id": respondent["_id"] + "-r",
                "collection_id": collection["_id"],
                "respondent_id": respondent["_id"],
                "survey_version": collection["survey_version"],
                "answers": {},
                "client_seq": 0,
                "progress": 0,
                "updated_at": _now(),
            }
        )

    token_str = create_respondent_token(respondent["_id"], collection["_id"])
    return {
        "token": token_str,
        "respondent": {
            "id": respondent["_id"],
            "label": respondent["label"],
            "status": update.get("status", respondent.get("status")),
        },
    }


def _resolve_display_answers(matrices_view: list[dict], raw_answers: dict) -> dict:
    out = {}
    for m in matrices_view:
        stored = raw_answers.get(m["matrix_id"], {})
        resolved = {}
        for p in m["pairs"]:
            pid = pair_id(p["uuid_a"], p["uuid_b"])
            if pid not in stored:
                continue
            v = stored[pid]
            lo, _hi = sorted([p["uuid_a"], p["uuid_b"]])
            resolved[pid] = v if p["uuid_a"] == lo else (1.0 / v)
        out[m["matrix_id"]] = resolved
    return out


@router.get("/api/respond/{token}/me")
async def respond_me(token: str, request: Request):
    payload = current_respondent(request)
    collection = await _collection_by_token(token)
    if collection["_id"] != payload["collection_id"]:
        raise HTTPException(403, "이 링크의 응답자가 아닙니다")

    respondent = await respondents_db.find_one({"_id": payload["respondent_id"]})
    resp = await responses_db.find_one(
        {"collection_id": collection["_id"], "respondent_id": payload["respondent_id"]}
    )
    survey, nodes_by_id = await _survey_and_nodes(collection)
    matrices_view = _build_matrices_view(survey, nodes_by_id)

    return {
        "respondent": {
            "id": respondent["_id"],
            "label": respondent["label"],
            "status": respondent.get("status", "in_progress"),
        },
        "answers": _resolve_display_answers(
            matrices_view, resp.get("answers", {}) if resp else {}
        ),
        "client_seq": resp.get("client_seq", 0) if resp else 0,
        "survey_version": collection["survey_version"],
    }


@router.put("/api/respond/{token}/answer")
async def put_answer(token: str, request: Request):
    payload = current_respondent(request)
    collection = await _collection_by_token(token)
    if collection["_id"] != payload["collection_id"]:
        raise HTTPException(403, "이 링크의 응답자가 아닙니다")
    if collection.get("status") != "open":
        raise HTTPException(410, "이 설문은 마감되었습니다")

    body = await request.json()
    matrix_id = body["matrix_id"]
    uuid_a, uuid_b = body["uuid_a"], body["uuid_b"]
    value = float(body["value"])
    client_seq = int(body.get("client_seq", 0))

    survey, _nodes = await _survey_and_nodes(collection)
    matrix = next((m for m in survey["matrices"] if m["matrix_id"] == matrix_id), None)
    if not matrix:
        raise HTTPException(404, "해당 비교 항목을 찾을 수 없습니다")

    resp = await responses_db.find_one(
        {"collection_id": collection["_id"], "respondent_id": payload["respondent_id"]}
    )
    if not resp:
        raise HTTPException(404, "응답 세션을 찾을 수 없습니다")

    # 네트워크 재전송으로 옛 값이 새 값을 덮어쓰지 않도록, 더 낮은 seq는 무시한다
    # (PLAN.md 4.5) — ack만 그대로 돌려줘서 클라이언트가 재시도를 멈추게 한다.
    if client_seq and client_seq <= resp.get("client_seq", 0):
        return {"ack": client_seq, "stale": True}

    pid, stored_value = to_stored_pair(uuid_a, uuid_b, value)
    answers = dict(resp.get("answers", {}))
    matrix_answers = dict(answers.get(matrix_id, {}))
    matrix_answers[pid] = stored_value
    answers[matrix_id] = matrix_answers

    total_pairs = sum(
        len(m["child_uuids"]) * (len(m["child_uuids"]) - 1) // 2
        for m in survey["matrices"]
    )
    answered_pairs = sum(len(v) for v in answers.values())
    progress = round(100 * answered_pairs / total_pairs) if total_pairs else 100

    await responses_db.update_one(
        {"_id": resp["_id"]},
        {
            "$set": {
                "answers": answers,
                "updated_at": _now(),
                "progress": progress,
                "client_seq": max(client_seq, resp.get("client_seq", 0)),
            }
        },
    )
    await respondents_db.update_one(
        {"_id": payload["respondent_id"], "status": "not_started"},
        {"$set": {"status": "in_progress"}},
    )

    node_ids = matrix["child_uuids"]
    try:
        result = derive_weights(node_ids, matrix_answers)
        cr_info = {"complete": True, "cr": result.cr}
    except IncompleteMatrixError:
        cr_info = {"complete": False}

    # 응답자는 HTTP로만 저장하지만(더 안정적이니까), 관리자 콘솔에는 실시간으로
    # 알려준다 — "실시간 설문 응답을 관리자 화면에서 즉시 확인" 요구사항의
    # 핵심 경로. 관리자가 그 순간 콘솔을 안 보고 있어도 hub.publish는 그냥
    # 조용히 아무에게도 안 보내고 끝난다(구독자가 없으면 no-op).
    await hub.publish(
        collection["_id"],
        "progress",
        {"respondent_id": payload["respondent_id"], "progress": progress, **cr_info},
        only_role_prefix="admin",
    )

    return {"ack": client_seq, "progress": progress, **cr_info}


@router.post("/api/respond/{token}/submit")
async def submit(token: str, request: Request):
    payload = current_respondent(request)
    collection = await _collection_by_token(token)
    if collection["_id"] != payload["collection_id"]:
        raise HTTPException(403, "이 링크의 응답자가 아닙니다")

    resp = await responses_db.find_one(
        {"collection_id": collection["_id"], "respondent_id": payload["respondent_id"]}
    )
    if not resp:
        raise HTTPException(404, "응답을 찾을 수 없습니다")

    current_round = collection.get("round", 1)
    already = await submissions_db.find_one(
        {
            "collection_id": collection["_id"],
            "respondent_id": payload["respondent_id"],
            "round": current_round,
        }
    )
    if already:
        raise HTTPException(409, f"이미 {current_round}라운드에 제출했습니다")

    await submissions_db.insert_one(
        {
            "_id": resp["_id"] + f"-s{current_round}",
            "collection_id": collection["_id"],
            "respondent_id": payload["respondent_id"],
            "round": current_round,
            "survey_version": resp["survey_version"],
            "answers": resp.get("answers", {}),
            "submitted_at": _now(),
        }
    )
    await respondents_db.update_one(
        {"_id": payload["respondent_id"]}, {"$set": {"status": "submitted"}}
    )
    return {"status": "submitted"}
