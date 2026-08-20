"""오프라인(종이) 응답 입력 — 관리자가 직접 격자에 입력하거나 CSV로 반입한다."""

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, UploadFile, File

from app.auth import current_user
from app.db import (
    collections_db,
    surveys_db,
    hierarchies_db,
    respondents_db,
    responses_db,
    submissions_db,
    imports_db,
)
from app.services.ahp_calc import (
    to_stored_pair,
    pair_id,
    derive_weights,
    IncompleteMatrixError,
)
from app.services.csv_schema import CSV_COLUMNS, parse_value, format_value
from app.routes.collection_routes import _get_collection_checked

router = APIRouter()


def _now():
    return datetime.now(timezone.utc)


def _dedupe_label(base: str, existing_labels: set[str]) -> str:
    """같은 수집 회차 안에서 응답자 이름이 겹치면 "이름 (2)"처럼 구분자를 붙여
    유일하게 만든다 — 이름이 같으면 결과 화면·CSV 내보내기에서 서로 다른
    응답자를 구별할 수 없어진다(요청사항)."""
    if base not in existing_labels:
        return base
    n = 2
    while f"{base} ({n})" in existing_labels:
        n += 1
    return f"{base} ({n})"


async def _survey_and_nodes(collection: dict):
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    hierarchy = await hierarchies_db.find_one(
        {"project_id": survey["project_id"], "version": survey["hierarchy_version"]}
    )
    nodes_by_id = {n["uuid"]: n for n in hierarchy["nodes"]}
    for a in hierarchy.get("alternatives", []):
        nodes_by_id[a["uuid"]] = a
    return survey, nodes_by_id


@router.post("/api/entry/{collection_id}/respondent")
async def add_manual_respondent(collection_id: str, request: Request):
    collection = await _get_collection_checked(collection_id, request)
    if collection["mode"] != "offline":
        raise HTTPException(400, "오프라인 수집에서만 응답자를 직접 추가할 수 있습니다")

    body = await request.json()
    label = (body.get("label") or "").strip()
    if not label:
        n = await respondents_db.count_documents({"collection_id": collection_id})
        label = f"응답자 {n + 1}"

    existing_labels = {
        r["label"]
        async for r in respondents_db.find(
            {"collection_id": collection_id}, {"label": 1}
        )
    }
    label = _dedupe_label(label, existing_labels)

    rid = uuid.uuid4().hex
    doc = {
        "_id": rid,
        "collection_id": collection_id,
        "code_hash": None,
        "label": label,
        "source": "manual",
        "status": "in_progress",
        "attributes": body.get("attributes") or {},
        "consent_at": None,
        "created_at": _now(),
    }
    await respondents_db.insert_one(doc)
    await responses_db.insert_one(
        {
            "_id": uuid.uuid4().hex,
            "collection_id": collection_id,
            "respondent_id": rid,
            "survey_version": collection["survey_version"],
            "answers": {},
            "client_seq": 0,
            "progress": 0,
            "updated_at": _now(),
        }
    )
    return {"id": rid, "label": label}


@router.delete("/api/entry/{collection_id}/respondents/{respondent_id}")
async def delete_manual_respondent(
    collection_id: str, respondent_id: str, request: Request
):
    await _get_collection_checked(collection_id, request)
    r = await respondents_db.find_one(
        {"_id": respondent_id, "collection_id": collection_id}
    )
    if not r:
        raise HTTPException(404, "응답자를 찾을 수 없습니다")
    if r.get("source") != "manual":
        raise HTTPException(400, "직접 입력한 응답자만 여기서 삭제할 수 있습니다")
    await responses_db.delete_many(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    await submissions_db.delete_many(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    await respondents_db.delete_one({"_id": respondent_id})
    return {"status": "deleted"}


@router.get("/api/entry/{collection_id}/grid")
async def get_grid(collection_id: str, request: Request):
    collection = await _get_collection_checked(collection_id, request)
    survey, nodes_by_id = await _survey_and_nodes(collection)

    respondents = [
        r
        async for r in respondents_db.find({"collection_id": collection_id}).sort(
            "created_at", 1
        )
    ]
    responses_by_rid = {}
    async for resp in responses_db.find({"collection_id": collection_id}):
        responses_by_rid[resp["respondent_id"]] = resp.get("answers", {})

    matrices_out = []
    for m in survey["matrices"]:
        matrices_out.append(
            {
                "matrix_id": m["matrix_id"],
                "parent_name": nodes_by_id.get(m["parent_uuid"], {}).get("name", ""),
                "is_alternative": m.get("is_alternative", False),
                "children": [
                    {"uuid": cid, "name": nodes_by_id.get(cid, {}).get("name", cid)}
                    for cid in m["child_uuids"]
                ],
                # i<j 표시 순서 쌍 — PUT 때 그대로 uuid_a/uuid_b로 되돌려보내면 된다.
                "pairs": [
                    {"uuid_a": m["child_uuids"][i], "uuid_b": m["child_uuids"][j]}
                    for i in range(len(m["child_uuids"]))
                    for j in range(i + 1, len(m["child_uuids"]))
                ],
            }
        )

    def _answers_in_display_order(matrices, raw_answers):
        """저장 규약(사전순 min/max 방향)을 화면 표시 순서(child_uuids[i]/[j], i<j)
        방향으로 되돌린다 — 프런트가 저장 규약을 몰라도 되게 한다."""
        out = {}
        for m in matrices:
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

    def _cr_by_matrix(raw_answers: dict) -> dict:
        """응답자별 매트릭스별 CR을 서버가 매번 계산해 돌려준다. 프런트가
        직전 PUT 응답을 DOM에 임시 캐시해 두는 방식은 그리드를 다시 그릴 때마다
        (응답자 전환 등) 캐시가 통째로 사라져 "완료된 매트릭스인데도 CR이 안
        보이는" 문제로 이어졌었다 — 그 캐시를 아예 없애고 매번 서버 계산값을 쓴다."""
        out = {}
        for m in survey["matrices"]:
            if len(m["child_uuids"]) < 2:
                continue
            cr_info = _compute_cr_for_matrix(m, raw_answers)
            if cr_info["complete"]:
                out[m["matrix_id"]] = cr_info[
                    "cr"
                ]  # n<=2면 cr=None(정의상 무의미) — 그대로 전달
        return out

    return {
        "matrices": matrices_out,
        "respondents": [
            {
                "id": r["_id"],
                "label": r["label"],
                "status": r.get("status", "in_progress"),
                "answers": _answers_in_display_order(
                    matrices_out, responses_by_rid.get(r["_id"], {})
                ),
                "cr_by_matrix": _cr_by_matrix(responses_by_rid.get(r["_id"], {})),
            }
            for r in respondents
        ],
    }


def _compute_cr_for_matrix(matrix: dict, answers: dict) -> dict:
    node_ids = matrix["child_uuids"]
    pairs = answers.get(matrix["matrix_id"], {})
    try:
        result = derive_weights(node_ids, pairs)
        return {"complete": True, "cr": result.cr, "weights": result.weights}
    except IncompleteMatrixError as e:
        return {"complete": False, "missing": len(e.missing_pairs)}


@router.put("/api/entry/{collection_id}/answers")
async def put_answer(collection_id: str, request: Request):
    collection = await _get_collection_checked(collection_id, request)
    body = await request.json()
    respondent_id = body["respondent_id"]
    matrix_id = body["matrix_id"]
    uuid_a = body["uuid_a"]
    uuid_b = body["uuid_b"]
    value_a_over_b = float(body["value"])

    survey, _nodes = await _survey_and_nodes(collection)
    matrix = next((m for m in survey["matrices"] if m["matrix_id"] == matrix_id), None)
    if not matrix:
        raise HTTPException(404, "해당 비교 행렬을 찾을 수 없습니다")

    pid, stored_value = to_stored_pair(uuid_a, uuid_b, value_a_over_b)
    resp = await responses_db.find_one(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    if not resp:
        raise HTTPException(404, "응답 문서를 찾을 수 없습니다")

    answers = dict(resp.get("answers", {}))
    matrix_answers = dict(answers.get(matrix_id, {}))
    matrix_answers[pid] = stored_value
    answers[matrix_id] = matrix_answers

    await responses_db.update_one(
        {"_id": resp["_id"]},
        {"$set": {"answers": answers, "updated_at": _now()}},
    )

    # 이 응답자가 현재 라운드에 이미 제출까지 마쳤다면(오프라인은 CSV 반입 직후,
    # 실시간/온라인은 섹션 콘솔에서 관리자가 직접 고치는 경우) 그 스냅샷도 같이
    # 갱신한다 — 안 그러면 결과 화면은 submissions만 보므로 방금 고친 값이
    # 반영되지 않는다(respond_routes.submit의 "같은 라운드는 덮어쓴다" 원칙과 동일).
    current_round = collection.get("round", 1)
    await submissions_db.update_one(
        {
            "collection_id": collection_id,
            "respondent_id": respondent_id,
            "round": current_round,
        },
        {"$set": {"answers": answers, "submitted_at": _now()}},
    )

    return _compute_cr_for_matrix(matrix, answers)


@router.post("/api/entry/{collection_id}/respondents/{respondent_id}/submit")
async def submit_manual_respondent(
    collection_id: str, respondent_id: str, request: Request
):
    collection = await _get_collection_checked(collection_id, request)
    resp = await responses_db.find_one(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    if not resp:
        raise HTTPException(404, "응답을 찾을 수 없습니다")

    await submissions_db.insert_one(
        {
            "_id": uuid.uuid4().hex,
            "collection_id": collection_id,
            "respondent_id": respondent_id,
            "round": collection.get("round", 1),
            "survey_version": resp["survey_version"],
            "answers": resp.get("answers", {}),
            "submitted_at": _now(),
        }
    )
    await respondents_db.update_one(
        {"_id": respondent_id}, {"$set": {"status": "submitted"}}
    )
    return {"status": "submitted"}


@router.post("/api/entry/{collection_id}/import")
async def import_csv(
    collection_id: str, request: Request, file: UploadFile = File(...)
):
    collection = await _get_collection_checked(collection_id, request)
    if collection["mode"] != "offline":
        raise HTTPException(400, "CSV 반입은 오프라인 수집에서만 지원합니다")

    survey, nodes_by_id = await _survey_and_nodes(collection)
    matrices_by_parent_name = {}
    for m in survey["matrices"]:
        parent_name = nodes_by_id.get(m["parent_uuid"], {}).get("name", "")
        name_to_uuid = {
            nodes_by_id.get(c, {}).get("name", c): c for c in m["child_uuids"]
        }
        matrices_by_parent_name[parent_name] = {
            "matrix_id": m["matrix_id"],
            "name_to_uuid": name_to_uuid,
        }

    raw = await file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp949", errors="replace")

    reader = csv.DictReader(io.StringIO(text))
    missing_cols = set(CSV_COLUMNS) - set(reader.fieldnames or [])
    if missing_cols:
        raise HTTPException(400, f"CSV에 필요한 열이 없습니다: {sorted(missing_cols)}")

    errors, by_respondent = [], {}
    for i, row in enumerate(reader, start=2):  # 1행은 헤더
        label = (row.get("respondent") or "").strip()
        parent = (row.get("parent") or "").strip()
        item_a = (row.get("item_a") or "").strip()
        item_b = (row.get("item_b") or "").strip()
        if not (label and parent and item_a and item_b):
            errors.append(
                f"{i}행: respondent/parent/item_a/item_b 중 비어 있는 값이 있습니다"
            )
            continue

        m_info = matrices_by_parent_name.get(parent)
        if not m_info:
            errors.append(f"{i}행: '{parent}' 기준을 찾을 수 없습니다")
            continue
        uuid_a = m_info["name_to_uuid"].get(item_a)
        uuid_b = m_info["name_to_uuid"].get(item_b)
        if not uuid_a or not uuid_b:
            errors.append(
                f"{i}행: '{parent}' 아래에서 '{item_a}' 또는 '{item_b}'를 찾을 수 없습니다"
            )
            continue
        try:
            value = parse_value(row.get("value", ""))
        except ValueError as e:
            errors.append(f"{i}행: {e}")
            continue

        pid, stored = to_stored_pair(uuid_a, uuid_b, value)
        by_respondent.setdefault(label, {}).setdefault(m_info["matrix_id"], {})[pid] = (
            stored
        )

    if errors:
        return {"status": "error", "errors": errors[:50], "error_count": len(errors)}

    existing_labels = {
        r["label"]
        async for r in respondents_db.find(
            {"collection_id": collection_id}, {"label": 1}
        )
    }

    created = []
    for label, answers in by_respondent.items():
        label = _dedupe_label(label, existing_labels)
        existing_labels.add(label)
        rid = uuid.uuid4().hex
        await respondents_db.insert_one(
            {
                "_id": rid,
                "collection_id": collection_id,
                "code_hash": None,
                "label": label,
                "source": "manual",
                "status": "submitted",
                "attributes": {},
                "consent_at": None,
                "created_at": _now(),
            }
        )
        await responses_db.insert_one(
            {
                "_id": uuid.uuid4().hex,
                "collection_id": collection_id,
                "respondent_id": rid,
                "survey_version": collection["survey_version"],
                "answers": answers,
                "client_seq": 0,
                "progress": 100,
                "updated_at": _now(),
            }
        )
        await submissions_db.insert_one(
            {
                "_id": uuid.uuid4().hex,
                "collection_id": collection_id,
                "respondent_id": rid,
                "round": collection.get("round", 1),
                "survey_version": collection["survey_version"],
                "answers": answers,
                "submitted_at": _now(),
            }
        )
        created.append({"respondent_id": rid, "label": label})

    user = current_user(request)
    await imports_db.insert_one(
        {
            "_id": uuid.uuid4().hex,
            "collection_id": collection_id,
            "filename": file.filename,
            "uploaded_by": user["uid"],
            "row_count": sum(len(a) for a in by_respondent.values()),
            "validation": {"errors": [], "warnings": []},
            "created_at": _now(),
        }
    )

    return {"status": "ok", "created": created}
