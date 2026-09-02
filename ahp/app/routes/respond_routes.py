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
from app.services.consistency import worst_offending_pairs
from app.services.demographics import coerce_attributes, validate_required

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
    # 대안 비교 행렬(is_alternative)의 child_uuids는 기준 노드가 아니라 대안이라,
    # 같은 uuid 조회 경로(nodes_by_id)에 대안도 섞어 둬야 이름이 정상 표시된다.
    for a in hierarchy.get("alternatives", []):
        nodes_by_id[a["uuid"]] = a
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
                "is_alternative": m.get("is_alternative", False),
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

    active_matrix_id = None
    if collection["mode"] == "realtime" and collection.get("session_started"):
        idx = collection.get("active_section_index", 0)
        matrices = survey["matrices"]
        if 0 <= idx < len(matrices):
            active_matrix_id = matrices[idx]["matrix_id"]

    return {
        "collection": {
            "id": collection["_id"],
            "mode": collection["mode"],
            "status": collection.get("status", "open"),
            "label": collection.get("label"),
            "round": collection.get("round", 1),
            "session_started": collection.get("session_started", False),
            "active_matrix_id": active_matrix_id,
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
            "collect_demographics": (project or {})
            .get("settings", {})
            .get("collect_demographics", "off")
            == "on",
            "demographics": survey.get("demographics", []),
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
            "attributes": respondent.get("attributes", {}),
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

    respondent = await respondents_db.find_one({"_id": payload["respondent_id"]})
    if collection["mode"] == "realtime" and collection.get("session_started"):
        idx = collection.get("active_section_index", 0)
        matrices = survey["matrices"]
        active_matrix_id = (
            matrices[idx]["matrix_id"] if 0 <= idx < len(matrices) else None
        )
        is_revision = (respondent or {}).get("revision_matrix_id") == matrix_id
        if matrix_id != active_matrix_id and not is_revision:
            # 예외를 던지면 클라이언트 큐(flushQueue)가 이걸 "일시적 네트워크
            # 실패"로 오인해 지수 백오프로 영원히 재시도한다(정지된 seq 처리와
            # 같은 이유로 200 + 플래그를 쓴다, 위 stale 분기 참고). 정상 UI라면
            # 애초에 열리지 않은 섹션을 PUT할 방법이 없고, 유일한 경합 상황은
            # 응답 중 섹션이 넘어간 순간의 네트워크 경쟁 정도라 조용히 무시한다.
            return {"ack": client_seq, "gated": True}

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
        if (respondent or {}).get("revision_matrix_id") == matrix_id:
            await respondents_db.update_one(
                {"_id": payload["respondent_id"]},
                {"$unset": {"revision_matrix_id": ""}},
            )
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


@router.put("/api/respond/{token}/demographics")
async def put_demographics(token: str, request: Request):
    """모든 비교를 마친 뒤 제출 직전에 응답자가 입력하는 인구통계 정보.
    respondents.attributes 에 코드 기반으로 저장한다."""
    payload = current_respondent(request)
    collection = await _collection_by_token(token)
    if collection["_id"] != payload["collection_id"]:
        raise HTTPException(403, "이 링크의 응답자가 아닙니다")

    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    demographics = (survey or {}).get("demographics", [])

    body = await request.json()
    attributes, errors = coerce_attributes(demographics, body.get("answers") or {})
    if errors:
        raise HTTPException(400, " / ".join(errors[:5]))
    missing = validate_required(demographics, attributes)
    if missing:
        raise HTTPException(400, f"필수 항목을 입력해 주세요: {', '.join(missing)}")

    await respondents_db.update_one(
        {"_id": payload["respondent_id"]}, {"$set": {"attributes": attributes}}
    )
    return {"attributes": attributes}


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
    # 같은 라운드 안에서는 제출 후에도 CR을 보고 자율적으로 값을 조정해 다시
    # 제출할 수 있어야 한다(요청사항) — collection이 열려 있는 한 같은 라운드의
    # submissions 문서를 덮어쓴다. 라운드가 넘어가면(advance-round) round 값 자체가
    # 바뀌므로 이전 라운드 스냅샷은 그대로 보존된다.
    if already and collection.get("status") != "open":
        raise HTTPException(409, f"이미 {current_round}라운드에 제출했습니다")

    sub_id = already["_id"] if already else (resp["_id"] + f"-s{current_round}")
    await submissions_db.update_one(
        {"_id": sub_id},
        {
            "$set": {
                "collection_id": collection["_id"],
                "respondent_id": payload["respondent_id"],
                "round": current_round,
                "survey_version": resp["survey_version"],
                "answers": resp.get("answers", {}),
                "submitted_at": _now(),
            }
        },
        upsert=True,
    )
    await respondents_db.update_one(
        {"_id": payload["respondent_id"]}, {"$set": {"status": "submitted"}}
    )
    return {"status": "submitted"}


@router.get("/api/respond/{token}/summary")
async def respond_summary(token: str, request: Request):
    """제출 완료 화면에서 기준별 CR을 보여주기 위한 요약. 제출된(submissions)
    스냅샷 기준으로 계산한다 — 작업 중인 responses가 아니라 실제로 제출한 값이어야
    CR도 "제출한 답"과 일치한다."""
    payload = current_respondent(request)
    collection = await _collection_by_token(token)
    if collection["_id"] != payload["collection_id"]:
        raise HTTPException(403, "이 링크의 응답자가 아닙니다")

    current_round = collection.get("round", 1)
    sub = await submissions_db.find_one(
        {
            "collection_id": collection["_id"],
            "respondent_id": payload["respondent_id"],
            "round": current_round,
        }
    )
    if not sub:
        raise HTTPException(404, "제출된 응답을 찾을 수 없습니다")

    survey, nodes_by_id = await _survey_and_nodes(collection)
    matrices_view = _build_matrices_view(survey, nodes_by_id)
    cr_threshold = (
        (
            (await projects_db.find_one({"_id": survey["project_id"]}, {"settings": 1}))
            or {}
        )
        .get("settings", {})
        .get("cr_threshold", 0.1)
    )

    items = []
    for m in matrices_view:
        node_ids = [c["uuid"] for c in m["children"]]
        pairs = sub["answers"].get(m["matrix_id"], {})
        try:
            result = derive_weights(node_ids, pairs)
            worst_pair = None
            if len(node_ids) >= 3:
                # 이 응답자 본인의 판단 중 CR에 가장 큰 영향을 준(가장 모순적인)
                # 쌍 — 리뷰 화면에서 바로 강조해 보여주기 위함(요청사항).
                worst = worst_offending_pairs(node_ids, pairs, top_k=1)
                if worst:
                    worst_pair = {"uuid_a": worst[0].uuid_a, "uuid_b": worst[0].uuid_b}
            items.append(
                {
                    "matrix_id": m["matrix_id"],
                    "parent_name": m["parent_name"],
                    "cr": result.cr,
                    "worst_pair": worst_pair,
                }
            )
        except IncompleteMatrixError:
            continue

    return {"items": items, "cr_threshold": cr_threshold}
