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
from app.services.codes import (
    generate_code,
    hash_code,
    generate_access_token,
    dedupe_label,
    seq_letters,
)
from app.services.methods import get_method
from app.services.csv_schema import group_item_count
from app.services.hub import hub

router = APIRouter()

MODES = {"offline", "online", "realtime"}
MODE_LABELS_KO = {"offline": "오프라인", "online": "온라인", "realtime": "실시간"}
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
        "session_started": doc.get("session_started", False),
        "active_section_index": doc.get("active_section_index", 0),
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
        "label": (body.get("label") or "").strip() or f"{MODE_LABELS_KO[mode]} 수집",
        "status": "open",
        "round": 1,
        "section_rounds": {},
        # 실시간 모드 전용 — 참여자는 session_started가 True가 되기 전까지
        # 대기 화면만 본다(요청사항: 연구자가 시작을 눌러야 진행). 다른
        # 모드에서는 그냥 무시되는 값이다.
        "session_started": False,
        "active_section_index": 0,
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


async def _collection_seq_letter(collection: dict) -> str:
    """이 수집이 속한 프로젝트에서 몇 번째로 생성된 수집인지를 A, B, C… 문자로.
    (opened_at 순서 기준. 저장하지 않고 매번 계산 — 기존 수집도 자동 정합.)"""
    project = await _project_for_survey(collection["survey_id"])
    if not project:
        return "A"
    survey_ids = [
        s["_id"]
        async for s in surveys_db.find({"project_id": project["_id"]}, {"_id": 1})
    ]
    ordered = [
        c["_id"]
        async for c in collections_db.find(
            {"survey_id": {"$in": survey_ids}}, {"_id": 1}
        ).sort("opened_at", 1)
    ]
    try:
        return seq_letters(ordered.index(collection["_id"]))
    except ValueError:
        return seq_letters(len(ordered))


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

    letter = await _collection_seq_letter(doc)
    start = await respondents_db.count_documents({"collection_id": collection_id})
    existing_labels = {
        r["label"]
        async for r in respondents_db.find(
            {"collection_id": collection_id}, {"label": 1}
        )
    }

    issued = []
    for i in range(count):
        code = generate_code()
        rid = uuid.uuid4().hex
        label = dedupe_label(f"참여자 {letter}-{start + i + 1}", existing_labels)
        existing_labels.add(label)
        await respondents_db.insert_one(
            {
                "_id": rid,
                "collection_id": collection_id,
                "code": code,
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


@router.post(
    "/api/collections/{collection_id}/respondents/{respondent_id}/reissue-code"
)
async def reissue_code(collection_id: str, respondent_id: str, request: Request):
    """분실된 접속 코드를 재발급한다. 응답자 신원(label)과 지금까지의 진행 상황은
    그대로 유지하고 code/code_hash만 바꾼다 — 코드를 잃어버렸다고 진행 중이던
    응답까지 지울 필요는 없다(요청사항: 지나치게 과한 익명성 제약을 완화)."""
    await _get_collection_checked(collection_id, request)
    r = await respondents_db.find_one(
        {"_id": respondent_id, "collection_id": collection_id}
    )
    if not r:
        raise HTTPException(404, "응답자를 찾을 수 없습니다")
    if r.get("source") == "manual":
        raise HTTPException(400, "오프라인(직접 입력) 응답자는 접속 코드가 없습니다")

    code = generate_code()
    await respondents_db.update_one(
        {"_id": respondent_id},
        {"$set": {"code": code, "code_hash": hash_code(code)}},
    )
    return {"respondent_id": respondent_id, "code": code}


@router.delete("/api/collections/{collection_id}/respondents/{respondent_id}")
async def delete_respondent(collection_id: str, respondent_id: str, request: Request):
    """응답자 삭제(코드/링크 응답자 포함) — entry_routes의 delete_manual_respondent는
    source=='manual'(오프라인)만 다루므로, 온라인/실시간 응답자를 위한 대응 엔드포인트.
    분실된 코드를 재발급하는 대신 아예 지우고 새로 등록하는 관리 흐름을 지원한다."""
    await _get_collection_checked(collection_id, request)
    r = await respondents_db.find_one(
        {"_id": respondent_id, "collection_id": collection_id}
    )
    if not r:
        raise HTTPException(404, "응답자를 찾을 수 없습니다")
    await responses_db.delete_many(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    await submissions_db.delete_many(
        {"collection_id": collection_id, "respondent_id": respondent_id}
    )
    await respondents_db.delete_one({"_id": respondent_id})
    return {"status": "deleted"}


def respondent_progress_summary(groups: list[dict], answers: dict) -> dict:
    """이 응답자의 전체 진행률과 "가장 문제 있는" CR 하나를 요약한다.
    콘솔에서는 매트릭스별 CR을 전부 늘어놓기보다, 한눈에 "이 사람 뭔가
    이상하다"를 알 수 있는 게 더 쓸모 있어서 최댓값(worst) 하나만 보여준다."""
    total_items = sum(group_item_count(m) for m in groups)
    answered_items = sum(len(answers.get(m["group_id"], {})) for m in groups)
    progress = round(100 * answered_items / total_items) if total_items else 100

    worst_cr = None
    all_complete = True
    for m in groups:
        node_ids = m["child_uuids"]
        if len(node_ids) < 2:
            continue
        lr = get_method(m.get("method")).derive_local(m, answers.get(m["group_id"], {}))
        if not lr.complete:
            all_complete = False
            continue
        cr = lr.consistency.value if lr.consistency else None
        if cr is not None:
            worst_cr = cr if worst_cr is None else max(worst_cr, cr)

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
            "code": d.get("code"),
            "source": d.get("source", "web"),
            "status": d.get("status", "not_started"),
            "consent_at": d.get("consent_at"),
            "attributes": d.get("attributes", {}),
            **respondent_progress_summary(
                survey["groups"], responses_by_rid.get(d["_id"], {})
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
    update = {"round": new_round}
    if doc["mode"] == "realtime":
        # 새 라운드는 다시 첫 섹션부터 — 델파이 라운드는 매번 전체 계층을
        # 처음부터 다시 훑는다는 전제라, 지난 라운드에 열려 있던 섹션 인덱스를
        # 그대로 이어받으면 안 된다.
        update["active_section_index"] = 0
    await collections_db.update_one({"_id": doc["_id"]}, {"$set": update})
    await respondents_db.update_many(
        {"collection_id": collection_id, "status": "submitted"},
        {"$set": {"status": "in_progress"}, "$unset": {"revision_group_id": ""}},
    )
    await hub.publish(collection_id, "round.advanced", {"round": new_round})
    return {"round": new_round}


# ── 섹션(=계층 매트릭스) 단위 델파이 진행 ─────────────────────────────────────
# 전체 설문 라운드(위 advance_round, collections.round)와 별개로, 매트릭스 하나
# ("섹션")마다 독립된 라운드 카운터를 둔다. 현장에서 한 섹션에 대한 토론이 끝나면
# 관리자가 이 섹션만 다시 열어 응답자가 재조정하거나(section.unlock), 응답자와
# 확인한 값을 관리자가 콘솔에서 직접 입력할 수 있어야 한다(요청사항 — 후자는
# 기존 오프라인 입력 경로 PUT /api/entry/{collection_id}/answers를 그대로 재사용).


@router.get("/api/collections/{collection_id}/sections/{group_id}/snapshot")
async def section_snapshot(collection_id: str, group_id: str, request: Request):
    collection = await _get_collection_checked(collection_id, request)
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    matrix = next((m for m in survey["groups"] if m["group_id"] == group_id), None)
    if not matrix:
        raise HTTPException(404, "해당 항목을 찾을 수 없습니다")
    node_ids = matrix["child_uuids"]
    kind = matrix.get("kind", "pairwise")
    plugin = get_method(matrix.get("method"))
    total_pairs = group_item_count(matrix)

    respondents = [
        r async for r in respondents_db.find({"collection_id": collection_id})
    ]
    responses_by_rid = {
        r["respondent_id"]: r.get("answers", {})
        async for r in responses_db.find({"collection_id": collection_id})
    }

    rows = []
    answers_by_rid: dict[str, dict] = {}
    for r in respondents:
        pairs = responses_by_rid.get(r["_id"], {}).get(group_id, {})
        answers_by_rid[r["_id"]] = pairs
        cr = None
        if len(node_ids) >= 3 and pairs:
            lr = plugin.derive_local(matrix, pairs)
            if lr.complete and lr.consistency:
                cr = lr.consistency.value
        rows.append(
            {
                "respondent_id": r["_id"],
                "label": r["label"],
                "answered_pairs": len(pairs),
                "total_pairs": total_pairs,
                "cr": cr,
                "answers": pairs,
            }
        )

    # 응답자 간 편차가 큰 문항·그룹 전체의 재고 지점 — 방법이 책임진다
    # (쌍대비교: 항목별 이상치 + 쌍별 기하평균 병합. 그 외 방법은 각자 정의).
    outliers = plugin.response_outliers(matrix, answers_by_rid)
    worst = []
    if len(node_ids) >= 3:
        merged = plugin.merge_responses(
            matrix, [a for a in answers_by_rid.values() if a]
        )
        if merged:
            c = plugin.validate(matrix, merged)
            worst = c.detail if c else []

    return {
        "group_id": group_id,
        "kind": kind,
        "round": (collection.get("section_rounds") or {}).get(group_id, 1),
        "respondents": rows,
        "outliers": outliers,
        "worst_pairs": worst,
    }


@router.post("/api/collections/{collection_id}/sections/{group_id}/unlock")
async def unlock_section(collection_id: str, group_id: str, request: Request):
    """이 섹션(매트릭스)만 재응답 대상으로 다시 연다 — 이미 제출을 마친
    응답자도 이 매트릭스만 다시 편집할 수 있게 응답자 화면에 신호를 보낸다."""
    collection = await _get_collection_checked(collection_id, request)
    section_rounds = dict(collection.get("section_rounds") or {})
    section_rounds[group_id] = section_rounds.get(group_id, 1) + 1
    await collections_db.update_one(
        {"_id": collection_id}, {"$set": {"section_rounds": section_rounds}}
    )
    if collection["mode"] == "realtime":
        # 실시간 게이팅 하에서는 이미 지난 섹션에 대한 PUT이 서버에서 막혀
        # 있다(respond_routes.put_answer의 active_group_id 검사) — 전원에게
        # revision_group_id를 부여해야 실제로 다시 응답할 수 있다. 개별
        # 재조정 요청(request_individual_revision)과 같은 메커니즘을 전원
        # 대상으로 쓰는 것뿐이다.
        await respondents_db.update_many(
            {"collection_id": collection_id},
            {"$set": {"revision_group_id": group_id}},
        )
    await hub.publish(
        collection_id,
        "section.unlock",
        {"group_id": group_id, "round": section_rounds[group_id]},
    )
    return {"group_id": group_id, "round": section_rounds[group_id]}


# ── 실시간 델파이 세션 진행 ────────────────────────────────────────────────
# 위 섹션 스냅샷/재오픈은 "이미 다 끝난 응답을 사후에 다시 본다"는 전제였다.
# 여기부터는 요구사항의 진짜 실시간 흐름 — 참여자는 연구자가 시작하기 전까지
# 대기하고, 한 섹션을 마치면 다음 섹션이 열릴 때까지 다시 대기한다. 응답자
# 측 게이팅(어느 섹션을 PUT할 수 있는지)은 respond_routes.put_answer가
# active_section_index/revision_group_id를 보고 강제한다 — 여기 엔드포인트는
# 그 상태를 옮기고 알리기만 한다.


@router.post("/api/collections/{collection_id}/session/start")
async def start_session(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    if doc["mode"] != "realtime":
        raise HTTPException(400, "실시간 수집에서만 세션을 시작할 수 있습니다")
    survey = await surveys_db.find_one({"_id": doc["survey_id"]})
    if not survey or not survey["groups"]:
        raise HTTPException(400, "비교할 항목이 없습니다")

    await collections_db.update_one(
        {"_id": collection_id},
        {"$set": {"session_started": True, "active_section_index": 0}},
    )
    first_group_id = survey["groups"][0]["group_id"]
    await hub.publish(
        collection_id,
        "session.started",
        {"group_id": first_group_id, "section_index": 0},
    )
    return {"session_started": True, "group_id": first_group_id}


@router.post("/api/collections/{collection_id}/sections/advance")
async def advance_section(collection_id: str, request: Request):
    doc = await _get_collection_checked(collection_id, request)
    if doc["mode"] != "realtime":
        raise HTTPException(400, "실시간 수집에서만 섹션을 진행할 수 있습니다")
    if not doc.get("session_started"):
        raise HTTPException(400, "세션을 먼저 시작해 주세요")

    survey = await surveys_db.find_one({"_id": doc["survey_id"]})
    next_index = doc.get("active_section_index", 0) + 1
    done = next_index >= len(survey["groups"])
    await collections_db.update_one(
        {"_id": collection_id}, {"$set": {"active_section_index": next_index}}
    )
    next_group_id = None if done else survey["groups"][next_index]["group_id"]
    await hub.publish(
        collection_id,
        "section.advanced",
        {"group_id": next_group_id, "section_index": next_index, "done": done},
    )
    return {"section_index": next_index, "group_id": next_group_id, "done": done}


async def _matrix_and_answers(collection: dict, group_id: str):
    survey = await surveys_db.find_one({"_id": collection["survey_id"]})
    matrix = next(
        (m for m in (survey or {}).get("groups", []) if m["group_id"] == group_id),
        None,
    )
    if not matrix:
        raise HTTPException(404, "해당 항목을 찾을 수 없습니다")
    responses_by_rid = {
        r["respondent_id"]: r.get("answers", {}).get(group_id, {})
        async for r in responses_db.find({"collection_id": collection["_id"]})
    }
    return matrix, responses_by_rid


@router.post("/api/collections/{collection_id}/sections/{group_id}/reveal-group")
async def reveal_group_result(collection_id: str, group_id: str, request: Request):
    """이 섹션의 현재 응답을 모아 그룹 가중치·평균 CR·최악의 쌍을 계산해
    접속 중인 모든 참여자의 대기 화면에 실시간으로 보여준다(요청사항 5단계
    "집계된 설문 결과를 공개"). 상태를 저장하지 않는 라이브 알림이라 — 다시
    보여주려면 버튼을 한 번 더 누르면 된다."""
    collection = await _get_collection_checked(collection_id, request)
    matrix, responses_by_rid = await _matrix_and_answers(collection, group_id)
    node_ids = matrix["child_uuids"]
    pairs_list = [p for p in responses_by_rid.values() if p]
    if len(node_ids) < 2 or not pairs_list:
        raise HTTPException(400, "아직 공개할 만큼 응답이 모이지 않았습니다")

    project = await _project_for_survey(collection["survey_id"])
    plugin = get_method(matrix.get("method"))
    agg = plugin.aggregate_group(matrix, pairs_list, project.get("settings", {}))
    if not agg.complete:
        raise HTTPException(400, "완전한 응답이 아직 없어 집계할 수 없습니다")
    group_weights = agg.weights
    _m = agg.consistency.metrics if agg.consistency else {}
    avg_cr = _m.get("avg_cr") or _m.get("avg_cri")  # BWM 은 avg_cri

    # 그룹 재고 지점 — 방법이 raw 응답 병합·검증을 책임진다(쌍대비교는 쌍별
    # 기하평균, BWM 은 best/worst 최빈 + BO/OW 기하평균).
    worst = []
    if len(node_ids) >= 3:
        merged = plugin.merge_responses(matrix, pairs_list)
        if merged:
            c = plugin.validate(matrix, merged)
            worst = c.detail if c else []

    payload = {
        "group_id": group_id,
        "kind": matrix.get("kind", "pairwise"),
        "weights": group_weights,
        "avg_cr": avg_cr,
        "worst_pairs": worst,
    }
    await hub.publish(collection_id, "section.results", payload)
    return payload


@router.post(
    "/api/collections/{collection_id}/sections/{group_id}/reveal-individual/{respondent_id}"
)
async def reveal_individual_result(
    collection_id: str, group_id: str, respondent_id: str, request: Request
):
    """이 참여자 본인의 가중치·CR만 본인에게 공개한다(요청사항 5단계 "개별
    참여자의 결과 가중치, CR까지 공개")."""
    collection = await _get_collection_checked(collection_id, request)
    matrix, responses_by_rid = await _matrix_and_answers(collection, group_id)
    pairs = responses_by_rid.get(respondent_id, {})
    lr = get_method(matrix.get("method")).derive_local(matrix, pairs)
    if not lr.complete:
        raise HTTPException(400, "이 참여자의 응답이 아직 완전하지 않습니다")

    payload = {
        "group_id": group_id,
        "kind": matrix.get("kind", "pairwise"),
        "weights": lr.weights,
        "cr": lr.consistency.value if lr.consistency else None,
    }
    await hub.publish(
        collection_id,
        "section.individual_result",
        payload,
        only_role_prefix=f"respondent:{respondent_id}",
    )
    return payload


@router.post(
    "/api/collections/{collection_id}/sections/{group_id}/request-revision/{respondent_id}"
)
async def request_individual_revision(
    collection_id: str, group_id: str, respondent_id: str, request: Request
):
    """이 참여자 한 명만 이미 지난 섹션도 다시 조정할 수 있게 한다(요청사항
    5단계 "CR 값을 토대로 수정을 요구"). respond_routes.put_answer가
    revision_group_id를 확인해 실제로 PUT을 허용한다."""
    collection = await _get_collection_checked(collection_id, request)
    r = await respondents_db.find_one(
        {"_id": respondent_id, "collection_id": collection_id}
    )
    if not r:
        raise HTTPException(404, "응답자를 찾을 수 없습니다")
    await respondents_db.update_one(
        {"_id": respondent_id}, {"$set": {"revision_group_id": group_id}}
    )

    # 이 참여자 본인의 이 기준 답 중 가장 모순적인 쌍 + 응답형 추천값을 함께 보내
    # 수정 화면에서 "어디를 어떻게 고칠지"를 바로 보여준다.
    worst_pairs = []
    try:
        matrix, responses_by_rid = await _matrix_and_answers(collection, group_id)
        pairs = responses_by_rid.get(respondent_id, {})
        if len(matrix["child_uuids"]) >= 3 and pairs:
            c = get_method(matrix.get("method")).validate(matrix, pairs)
            worst_pairs = c.detail if c else []
    except Exception:
        worst_pairs = []

    await hub.publish(
        collection_id,
        "section.revision_requested",
        {"group_id": group_id, "worst_pairs": worst_pairs},
        only_role_prefix=f"respondent:{respondent_id}",
    )
    return {"status": "requested"}
